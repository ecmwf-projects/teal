# (C) Copyright 2020 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#


from abc import ABCMeta, abstractmethod

from earthkit.data.core.gridspec import GridSpec
from earthkit.data.core.metadata import RawMetadata

# grib keys -> gridspec keys
vocabulary = {
    "Nx": "nx",
    "Ny": "ny",
    "Ni": "ni",
    "Nj": "nj",
    "DxInMetres": "dx_in_metres",
    "DyInMetres": "dy_in_metres",
    "xDirectionGridLengthInMetres": "dx_in_metres",
    "yDirectionGridLengthInMetres": "dy_in_metres",
    "LaDInDegrees": "lad",
    "LoVInDegrees": "lov",
    "Latin1InDegrees": "latin1",
    "Latin2InDegrees": "latin2",
    "latitudeOfSouthernPoleInDegrees": "lat_south_pole",
    "longitudeOfSouthernPoleInDegrees": "lon_south_pole",
    "orientationOfTheGridInDegrees": "orientation",
    "jPointsAreConsecutive": "j_points_consecutive",
    "iScansNegatively": "i_scans_negatively",
    "jScansPositively": "j_scans_positively",
    "angleOfRotationInDegrees": "angle_of_rotation",
    "standardParallelInDegrees": "standard_parallel",
    "centralLongitudeInDegrees": "central_longitude",
    "shapeOfTheEarth": "shape_of_the_earth",
    "radius": "radius",
    "earthMajorAxis": "earth_major_axis",
    "earthMinorAxis": "earth_minor_axis",
}


def missing_is_none(x):
    return None if x == 2147483647 else x


def make_gridspec(metadata):
    grid_type = metadata.get("gridType", None)
    if grid_type in grid_specs:
        maker = grid_specs[grid_type]
        d = maker(metadata).make()
        return GridSpec(d)
    else:
        raise TypeError(f"Cannot make GridSpec, unsupported grid_type={grid_type}")


class GridSpecMaker(metaclass=ABCMeta):
    POSITIVE_SCAN_DIR = 1
    NEGATIVE_SCAN_DIR = -1
    GRID_TYPE = None
    ROTATED = None

    def __init__(self, md):
        if isinstance(md, dict):
            md = RawMetadata(md)
        self.md = md
        assert md.get("gridType", None) == self.GRID_TYPE

    def _get_first_valid(self, keys, desc=""):
        for k in keys:
            v = self.md.get(k, None)
            if v is not None:
                return v
        if desc:
            raise ValueError(f"Could not determine {desc}")
        else:
            raise ValueError(f"None of the keys have valid value: {keys}")

    def first_lon(self):
        return self.md.get("longitudeOfFirstGridPointInDegrees")

    def last_lon(self):
        return self.md.get("longitudeOfLastGridPointInDegrees", None)

    def first_lat(self):
        return self.md.get("latitudeOfFirstGridPointInDegrees", None)

    def last_lat(self):
        return self.md.get("latitudeOfLastGridPointInDegrees", None)

    def north(self):
        return max(self.first_lat(), self.last_lat())

    def south(self):
        return min(self.first_lat(), self.last_lat())

    def west(self):
        if self.x_scan_dir() == self.POSITIVE_SCAN_DIR:
            return self.first_lon()
        else:
            return self.last_lon()

    def east(self):
        if self.x_scan_dir() == self.POSITIVE_SCAN_DIR:
            return self.last_lon()
        else:
            return self.first_lon()

    def rotation(self):
        return [
            self.md.get("latitudeOfSouthernPoleInDegrees", None),
            self.md.get("longitudeOfSouthernPoleInDegrees", None),
        ]

    def x_scan_dir(self):
        v = self.md.get("iScansNegatively", None)
        if v is not None:
            return self.POSITIVE_SCAN_DIR if v == 0 else self.NEGATIVE_SCAN_DIR
        else:
            v = self.md.get("iScansPositively", None)
            if v is not None:
                return self.POSITIVE_SCAN_DIR if v == 1 else self.NEGATIVE_SCAN_DIR
            else:
                raise ValueError("Could not determine i-direction scanning mode")

    @abstractmethod
    def make(self):
        pass

    def _add(self, key, d):
        if isinstance(key, list):
            for k in key:
                self._add_one(k, d)
        else:
            self._add_one(key, d)

    def _add_one(self, key, d):
        v = self.md.get(key, None)
        if v is not None:
            k = vocabulary.get(key, None)
            if k is not None:
                d[k] = v
            else:
                raise ValueError(f"key={key} not found in vocabulary")

    def _add_rotation(self, d):
        if self.ROTATED:
            d["rotation"] = [
                self.md.get("latitudeOfSouthernPoleInDegrees", None),
                self.md.get("longitudeOfSouthernPoleInDegrees", None),
            ]
            self._add("angleOfRotationInDegrees", d)

    def _add_scan_mode(self, d):
        keys = [
            "jPointsAreConsecutive",
            "iScansNegatively",
            "jScansPositively",
        ]
        self._add(keys, d)

    def _add_earth(self, d):
        keys = ["shapeOfTheEarth", "radius", "earthMajorAxis", "earthMinorAxis"]
        self._add(keys, d)


class LatLonGridSpecMaker(GridSpecMaker):
    GRID_TYPE = "regular_ll"
    ROTATED = False

    def make(self):
        d = dict()
        d["type"] = self.GRID_TYPE
        dx, dy = self._get_grid()
        d["grid"] = [abs(dx), abs(dy)]
        d["area"] = [self.north(), self.west(), self.south(), self.east()]

        self._add_rotation(d)
        self._add_scan_mode(d)
        return d

    def _get_grid(self):
        dx = self.md.get("iDirectionIncrementInDegrees", None)
        dy = self.md.get("jDirectionIncrementInDegrees", None)

        if dx is None:
            nx = self._get_first_valid(
                ["numberOfPointsAlongAParallel", "Ni"],
                desc="number of points in longitude",
            )
            lon_range = self.last_lon() - self.first_lon()
            if nx == 1:
                dx = 1.0
            else:
                dx = lon_range / (nx - 1.0)

        if dy is None:
            ny = self._get_first_valid(
                ["numberOfPointsAlongAMeridian", "Nj"],
                desc="number of points in latitude",
            )
            lat_range = self.last_lat() - self.first_lat()
            if ny == 1:
                dy = 1.0
            else:
                dy = lat_range / (ny - 1.0)

        return dx, dy


class ReducedLatLonGridSpecMaker(LatLonGridSpecMaker):
    GRID_TYPE = "reduced_ll"
    ROTATED = False

    def make(self):
        d = dict()
        d["type"] = self.GRID_TYPE
        _, dy = self._get_grid()
        d["grid"] = abs(dy)
        d["area"] = [self.north(), self.west(), self.south(), self.east()]

        self._add_rotation(d)
        self._add_scan_mode(d)
        return d

    def _get_grid(self):
        dy = self.md.get("jDirectionIncrementInDegrees", None)

        if dy is None:
            ny = self._get_first_valid(
                ["numberOfPointsAlongAMeridian", "Nj"],
                desc="number of points in latitude",
            )
            lat_range = self.last_lat() - self.first_lat()
            if ny == 1:
                dy = 1.0
            else:
                dy = lat_range / (ny - 1.0)

        return None, dy


class RotatedLatLonGridSpecMaker(LatLonGridSpecMaker):
    GRID_TYPE = "rotated_ll"
    ROTATED = True


class GaussianGridSpecMaker(GridSpecMaker):
    def __init__(self, *args, label=None):
        if label not in ["F", "N", "O"]:
            raise ValueError("Invalid Gaussian grid label={label}")
        self.label = label
        super().__init__(*args)

    def make(self):
        d = dict()
        d["type"] = self.GRID_TYPE
        N = self.md.get("N")
        global_grid = self.md.get("global", 0) == 1
        d["grid"] = f"{self.label}{N}"
        if not global_grid:
            d["area"] = [self.north(), self.west(), self.south(), self.east()]

        self._add_rotation(d)
        self._add_scan_mode(d)
        return d

    def west(self):
        return self.first_lon()

    def east(self):
        return self.last_lon()


class RegularGaussianGridSpecMaker(GaussianGridSpecMaker):
    GRID_TYPE = "regular_gg"
    ROTATED = False

    def __init__(self, md):
        super().__init__(md, label="F")


class ReducedGaussianGridSpecMaker(GaussianGridSpecMaker):
    GRID_TYPE = "reduced_gg"
    ROTATED = False

    def __init__(self, md):
        octahedral = md.get("isOctahedral", 0) == 1
        label = "O" if octahedral else "N"
        super().__init__(md, label=label)


class RegularRotatedGaussianGridSpecMaker(RegularGaussianGridSpecMaker):
    GRID_TYPE = "rotated_gg"
    ROTATED = True


class ReducedRotatedGaussianGridSpecMaker(ReducedGaussianGridSpecMaker):
    GRID_TYPE = "reduced_rotated_gg"
    ROTATED = True


class MercatorGridSpecMaker(GridSpecMaker):
    GRID_TYPE = "mercator"
    ROTATED = False

    def make(self):
        d = dict()
        d["type"] = self.GRID_TYPE
        dx, dy = self._get_grid()
        d["grid"] = [abs(dx), abs(dy)]
        d["area"] = [self.north(), self.west(), self.south(), self.east()]

        keys = [
            "Ni",
            "Nj",
            "LaDInDegrees",
            "orientationOfTheGridInDegrees",
        ]
        self._add(keys, d)
        self._add_scan_mode(d)
        return d

    def _get_grid(self):
        dx = self.md.get("DiInMetres")
        dy = self.md.get("DjInMetres")
        return dx, dy


class PolarStereographicGridSpecMaker(GridSpecMaker):
    GRID_TYPE = "polar_stereographic"
    ROTATED = False

    def make(self):
        d = dict()
        d["type"] = self.GRID_TYPE
        dx, dy = self._get_grid()
        d["grid"] = [abs(dx), abs(dy)]
        d["first_point"] = [self.first_lat(), self.first_lon()]

        keys = [
            "Nx",
            "Ny",
            "LaDInDegrees",
            "orientationOfTheGridInDegrees",
        ]
        self._add(keys, d)

        self._add_scan_mode(d)
        return d

    def _get_grid(self):
        dx = self.md.get("DxInMetres")
        dy = self.md.get("DyInMetres")
        return dx, dy


class LambertGridSpecMaker(GridSpecMaker):
    GRID_TYPE = "lambert"
    ROTATED = False

    def make(self):
        d = dict()
        d["type"] = self.GRID_TYPE
        dx, dy = self._get_grid()
        d["grid"] = [abs(dx), abs(dy)]
        d["first_point"] = [self.first_lat(), self.first_lon()]

        keys = [
            "Nx",
            "Ny",
            "LaDInDegrees",
            "LoVInDegrees",
            "LatIn1InDegrees",
            "LatIn2InDegrees",
        ]
        self._add(keys, d)
        self._add_scan_mode(d)
        return d

    def _get_grid(self):
        dx = self.md.get("DxInMetres")
        dy = self.md.get("DyInMetres")
        return dx, dy


class LambertAEAGridSpecMaker(GridSpecMaker):
    GRID_TYPE = "lambert_azimuthal_equal_area"
    ROTATED = False

    def make(self):
        d = dict()
        d["type"] = self.GRID_TYPE
        dx, dy = self._get_grid()
        d["grid"] = [abs(dx), abs(dy)]
        d["first_point"] = [self.first_lat(), self.first_lon()]

        keys = [
            "Nx",
            "Ny",
            "standardParallelInDegrees",
            "centralLongitudeInDegrees",
        ]
        self._add(keys, d)

        self._add_scan_mode(d)
        return d

    def _get_grid(self):
        dx = self._get_first_valid(
            ["DyInMetres", "xDirectionGridLengthInMetres"],
            desc="x grid increment in metres",
        )
        dy = self._get_first_valid(
            ["DyInMetres", "yDirectionGridLengthInMetres"],
            desc="y grid increment in metres",
        )
        return dx, dy


grid_specs = {}
for g in [
    LatLonGridSpecMaker,
    ReducedLatLonGridSpecMaker,
    RotatedLatLonGridSpecMaker,
    RegularGaussianGridSpecMaker,
    ReducedGaussianGridSpecMaker,
    RegularRotatedGaussianGridSpecMaker,
    ReducedRotatedGaussianGridSpecMaker,
    MercatorGridSpecMaker,
    PolarStereographicGridSpecMaker,
    LambertGridSpecMaker,
    LambertAEAGridSpecMaker,
]:
    grid_specs[g.GRID_TYPE] = g
