#!/usr/bin/env python3

# (C) Copyright 2020 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#

import numpy as np

from earthkit.data import from_source
from earthkit.data.core.temporary import temp_file
from earthkit.data.testing import earthkit_examples_file


def test_target_grib_1():
    ds = from_source("file", earthkit_examples_file("test.grib"))
    vals_ref = ds.values[:, :4]

    with temp_file() as path:
        ds.to_target("file", path)

        ds1 = from_source("file", path)
        assert len(ds) == len(ds1)
        assert ds1.metadata("shortName") == ["2t", "msl"]
        assert np.allclose(ds1.values[:, :4], vals_ref)


def test_target_grib_save_compat():
    ds = from_source("file", earthkit_examples_file("test.grib"))
    vals_ref = ds.values[:, :4]

    with temp_file() as path:
        ds.save(path)

        ds1 = from_source("file", path)
        assert len(ds) == len(ds1)
        assert ds1.metadata("shortName") == ["2t", "msl"]
        assert np.allclose(ds1.values[:, :4], vals_ref)


def test_writers_core():
    # from earthkit.data.targets.file import FileTarget
    # from earthkit.data.targets import Target

    # from earthkit.data.targets import find_target
    # from earthkit.data.writers import to_target
    # from earthkit.data.writers import write

    # assert Target
    # assert find_target
    # assert write

    ds = from_source("file", earthkit_examples_file("test.grib"))
    vals_ref = ds.values[:, :4]

    with temp_file() as path:
        ds.to_target("file", path)

        # assert path.exists()

        ds1 = from_source("file", path)
        assert len(ds) == len(ds1)
        assert ds1.metadata("shortName") == ["2t", "msl"]
        assert np.allclose(ds1.values[:, :4], vals_ref)

    # write("file", ds, file=temp_file())
    # write("file", ds, encoder="grib", file=temp_file())

    # target = FileTarget(temp_file())
    # target.write(ds)
    # target.write(ds, encoder="grib")

    # to_target("file", ds, file=temp_file())
    # ds.to_target("file", file=temp_file(), encoder="grib")

    # to_target("fdb", ds, conf="myconf")
    # ds.to_target("fdb", conf="myconf")
    # target = FdbTarget("myconf")
    # target.write(ds)
    # target.write(ds, format="grib")
    # target.write(ds, encoder="grib")
