# (C) Copyright 2020 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#

import functools
import getpass
import logging
import os
import tempfile
from contextlib import contextmanager
from typing import Callable

import yaml

from earthkit.data import __version__ as VERSION
from earthkit.data.utils.html import css
from earthkit.data.utils.humanize import (
    as_bytes,
    as_percent,
    as_seconds,
    interval_to_human,
)
from earthkit.data.utils.interval import Interval

LOG = logging.getLogger(__name__)

DOT_EARTHKIT_DATA = os.path.expanduser("~/.earthkit_data")


class Validator:
    def check(self, value):
        raise NotImplementedError()

    def explain(self):
        return str()


class IntervalValidator(Validator):
    def __init__(self, interval):
        self.interval = interval

    def check(self, value):
        return value in self.interval

    def explain(self):
        return f"Valid when {interval_to_human(self.interval)}."


class Setting:
    def __init__(
        self,
        default,
        description,
        getter=None,
        none_ok=False,
        kind=None,
        docs_default=None,
        validator=None,
    ):
        self.default = default
        self.description = description
        self.getter = getter
        self.none_ok = none_ok
        self.kind = kind if kind is not None else type(default)
        self.docs_default = docs_default if docs_default is not None else self.default
        self.validator = validator

    def kind(self):
        return type(self.default)

    def save(self, name, value, f):
        for n in self.description.split("\n"):
            print(f"# {n.strip()}", file=f)
        print(file=f)
        comment = yaml.dump({name: self.default}, default_flow_style=False)
        for n in comment.split("\n"):
            if n:
                print(f"# {n}", file=f)
        if value != self.default:
            print(file=f)
            yaml.dump({name: value}, f, default_flow_style=False)

    @property
    def docs_description(self):
        d = self.description
        if self.validator:
            t = self.validator.explain()
            if t:
                return d + " " + t
        return d


_ = Setting


SETTINGS_AND_HELP = {
    "cache-directory": _(
        os.path.join(tempfile.gettempdir(), "earthkit-data-%s" % (getpass.getuser(),)),
        """Directory of where the dowloaded files are cached, with ``${USER}`` is the user id.
        See :doc:`/guide/caching` for more information.""",
        docs_default=os.path.join("TMP", "earthkit-data-%s" % (getpass.getuser(),)),
    ),
    "dask-directories": _(
        [os.path.join(DOT_EARTHKIT_DATA, "dask")],
        """List of directories where to search for dask cluster definitions.
        See :ref:`dask` for more information.""",
    ),
    "datasets-directories": _(
        [os.path.join(DOT_EARTHKIT_DATA, "datasets")],
        """List of directories where to search for datasets definitions.
        See :ref:`datasets` for more information.""",
    ),
    "datasets-catalogs-urls": _(
        ["https://github.com/ecmwf-lab/climetlab-datasets/raw/main/datasets"],
        """List of url where to search for catalogues of datasets definitions.
        See :ref:`datasets` for more information.""",
    ),
    "number-of-download-threads": _(
        5,
        """Number of threads used to download data.""",
    ),
    "cache-policy": _("persistent", "Caching policy"),
    "maximum-cache-size": _(
        None,
        """Maximum disk space used by the earthkit-data cache (ex: 100G or 2T).""",
        getter="_as_bytes",
        none_ok=True,
    ),
    "maximum-cache-disk-usage": _(
        "95%",
        """Disk usage threshold after which earthkit-data expires older cached
        entries (% of the full disk capacity).
        See :doc:`/guide/caching` for more information.""",
        getter="_as_percent",
    ),
    "url-download-timeout": _(
        "30s",
        """Timeout when downloading from an url.""",
        getter="_as_seconds",
    ),
    "check-out-of-date-urls": _(
        True,
        "Perform a HTTP request to check if the remote version of a cache file has changed",
    ),
    "download-out-of-date-urls": _(
        False,
        "Re-download URLs when the remote version of a cached file as been changed",
    ),
    "use-standalone-mars-client-when-available": _(
        True,
        "Use the standalone mars client when available instead of using the web API.",
    ),
    "reader-type-check-bytes": _(
        64,
        "Number of bytes read from the beginning of a source to identify its type.",
        validator=IntervalValidator(Interval(8, 4096)),
    ),
}


NONE = object()
DEFAULTS = {}
for k, v in SETTINGS_AND_HELP.items():
    DEFAULTS[k] = v.default


@contextmanager
def new_settings(s):
    SETTINGS._stack.append(s)
    try:
        yield None
    finally:
        SETTINGS._stack.pop()
        SETTINGS._notify()


def forward(func):
    @functools.wraps(func)
    def wrapped(self, *args, **kwargs):
        if self._stack:
            return func(self._stack[-1], *args, **kwargs)
        return func(self, *args, **kwargs)

    return wrapped


def save_settings(path, settings):
    LOG.debug("Saving settings")
    with open(path, "w") as f:
        print("# This file is automatically generated", file=f)
        print(file=f)

        for k, v in sorted(settings.items()):
            h = SETTINGS_AND_HELP.get(k)
            if h:
                print(file=f)
                print("#", "-" * 76, file=f)
                h.save(k, v, f)

        print(file=f)
        print("#", "-" * 76, file=f)
        print("# Version of CliMetLab", file=f)
        print(file=f)
        yaml.dump({"version": VERSION}, f, default_flow_style=False)
        print(file=f)


class Settings:
    def __init__(self, settings_yaml: str, defaults: dict, callbacks=[]):
        self._defaults = defaults
        self._settings = dict(**defaults)
        self._callbacks = [c for c in callbacks]
        self._settings_yaml = settings_yaml
        self._pytest = None
        self._stack = []

    @forward
    def get(self, name: str, default=NONE):
        """[summary]

        Parameters
        ----------
            name: str
                [description]
            default: [type]
                [description]. Defaults to NONE.

        Returns
        -------
            [type]: [description]
        """
        if name not in SETTINGS_AND_HELP:
            raise KeyError("No setting name '%s'" % (name,))

        getter, none_ok = (
            SETTINGS_AND_HELP[name].getter,
            SETTINGS_AND_HELP[name].none_ok,
        )
        if getter is None:
            getter = lambda name, value, none_ok: value  # noqa: E731
        else:
            getter = getattr(self, getter)

        if default is NONE:
            return getter(name, self._settings[name], none_ok)

        return getter(name, self._settings.get(name, default), none_ok)

    @forward
    def set(self, name: str, *args, **kwargs):
        """[summary]

        Parameters
        ----------
            name: str
                [description]
            value: [type]
                [description]
        """
        if name not in SETTINGS_AND_HELP:
            raise KeyError("No setting name '%s'" % (name,))

        klass = SETTINGS_AND_HELP[name].kind

        if klass in (bool, int, float, str):
            # TODO: Proper exceptions
            assert len(args) == 1
            assert len(kwargs) == 0
            value = args[0]
            value = klass(value)

        if klass is list:
            assert len(args) > 0
            assert len(kwargs) == 0
            value = list(args)
            if len(args) == 1 and isinstance(args[0], list):
                value = args[0]

        if klass is dict:
            assert len(args) <= 1
            if len(args) == 0:
                assert len(kwargs) > 0
                value = kwargs

            if len(args) == 1:
                assert len(kwargs) == 0
                value = args[0]

        getter, none_ok = (
            SETTINGS_AND_HELP[name].getter,
            SETTINGS_AND_HELP[name].none_ok,
        )
        if getter is not None:
            assert len(args) == 1
            assert len(kwargs) == 0
            value = args[0]
            # Check if value is properly formatted for getter
            getattr(self, getter)(name, value, none_ok)
        else:
            if not isinstance(value, klass):
                raise TypeError("Setting '%s' must be of type '%s'" % (name, klass))

        validator = SETTINGS_AND_HELP[name].validator
        if validator is not None:
            if not validator.check(value):
                raise ValueError(
                    f"Settings {name} cannot be set to {value}. {validator.explain()}"
                )

        self._settings[name] = value
        self._changed()

    @forward
    def reset(self, name: str = None):
        """Reset setting(s) to default values.

        Parameters
        ----------
            name: str, optional
                The name of the setting to reset to default. If the setting
                does not have a default, it is removed. If `None` is passed, all settings are
                reset to their default values. Defaults to None.
        """
        if name is None:
            self._settings = dict(**DEFAULTS)
        else:
            if name not in DEFAULTS:
                raise KeyError("No setting name '%s'" % (name,))

            self._settings.pop(name, None)
            if name in DEFAULTS:
                self._settings[name] = DEFAULTS[name]
        self._changed()

    @forward
    def _repr_html_(self):
        html = [css("table")]
        html.append("<table class='climetlab'>")
        for k, v in sorted(self._settings.items()):
            setting = SETTINGS_AND_HELP.get(k, None)
            default = setting.default if setting else ""
            html.append("<tr><td>%s</td><td>%r</td><td>%r</td></td>" % (k, v, default))
        html.append("</table>")
        return "".join(html)

    @forward
    def dump(self):
        for k, v in sorted(self._settings.items()):
            yield ((k, v, SETTINGS_AND_HELP.get(k)))

    def _changed(self):
        self._save()
        self._notify()

    def _notify(self):
        for cb in self._callbacks:
            cb()

    def on_change(self, callback: Callable[[], None]):
        self._callbacks.append(callback)

    def _save(self):
        if self._settings_yaml is None:
            return

        try:
            save_settings(self._settings_yaml, self._settings)
        except Exception:
            LOG.error(
                "Cannot save CliMetLab settings (%s)",
                self._settings_yaml,
                exc_info=True,
            )

    def _as_bytes(self, name, value, none_ok):
        return as_bytes(value, name=name, none_ok=none_ok)

    def _as_percent(self, name, value, none_ok):
        return as_percent(value, name=name, none_ok=none_ok)

    def _as_seconds(self, name, value, none_ok):
        return as_seconds(value, name=name, none_ok=none_ok)

    # def _as_number(self, name, value, units, none_ok):
    #     return as_number(name, value, units, none_ok)

    @forward
    def temporary(self, name=None, *args, **kwargs):
        tmp = Settings(None, self._settings, self._callbacks)
        if name is not None:
            tmp.set(name, *args, **kwargs)
        return new_settings(tmp)


save = False
settings_yaml = os.path.expanduser(os.path.join(DOT_EARTHKIT_DATA, "settings.yaml"))

try:
    if not os.path.exists(DOT_EARTHKIT_DATA):
        os.mkdir(DOT_EARTHKIT_DATA, 0o700)
    if not os.path.exists(settings_yaml):
        save_settings(settings_yaml, DEFAULTS)
except Exception:
    LOG.error(
        "Cannot create earthkit-data settings directory, using defaults (%s)",
        settings_yaml,
        exc_info=True,
    )

settings = dict(**DEFAULTS)
try:
    with open(settings_yaml) as f:
        s = yaml.load(f, Loader=yaml.SafeLoader)
        if not isinstance(s, dict):
            s = {}

        settings.update(s)

    # if s != settings:
    #     save = True

    if settings.get("version") != VERSION:
        save = True

except Exception:
    LOG.error(
        "Cannot load earthkit-data settings (%s), reverting to defaults",
        settings_yaml,
        exc_info=True,
    )

SETTINGS = Settings(settings_yaml, settings)
if save:
    SETTINGS._save()
