# (C) Copyright 2022 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.

import pandas as pd

from earthkit.data.translators import Translator


class PandasSeriesTranslator(Translator):
    """Translator class for pandas `Series`"""

    def __init__(self, data, *args, **kwargs):
        self.data = data.to_pandas(*args, **kwargs)

    def __call__(self):
        """
        Series requested, if DataFrame return the first column
        """
        if isinstance(self.data, pd.DataFrame):
            return self.data.iloc[:, 0]

        return self.data


class PandasDataFrameTranslator(PandasSeriesTranslator):
    """Translator class for pandas `DataFrame`"""

    def __call__(self):
        """
        DataFrame requested, if Series convert to DataFrame.
        """
        if isinstance(self.data, pd.Series):
            return self.data.to_frame()

        return self.data


class GeoPandasDataFrameTranslator(PandasSeriesTranslator):
    """Translator class for geopandas `DataFrame`"""

    def __call__(self):
        """
        GeoDataFrame requested, if normal pandas convert to geopandas.
        """
        import geopandas as gpd

        if isinstance(self.data, pd.DataFrame):
            return gpd.GeoDataFrame(self.data)

        return self.data


def translator(data, cls, *args, **kwargs):
    try:
        import geopandas as gpd

        l_gpd = True
    except ImportError:
        l_gpd = False

    if l_gpd and cls in [gpd.geodataframe.GeoDataFrame]:
        return GeoPandasDataFrameTranslator(data, *args, **kwargs)
    if cls in [pd.DataFrame]:
        return PandasDataFrameTranslator(data, *args, **kwargs)
    if cls in [pd.Series]:
        return PandasSeriesTranslator(data, *args, **kwargs)

    return None
