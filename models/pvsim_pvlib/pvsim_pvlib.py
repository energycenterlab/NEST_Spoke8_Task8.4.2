"""
A PV standalone simulator based on pvlib library. It implements different models for calculation:
    - PVGIS model
    - Simplified pvlib (under dev)
    - Detailed pvlib (under dev)

"""
from loguru import logger as log
import functools
import pandas as pd
import pvlib
from pvlib.pvsystem import PVSystem, Array, FixedMount
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.iotools import get_pvgis_hourly

__author__ = "Daniele Salvatore Schiera"
__credits__ = ["Daniele Salvatore Schiera"]
__license__ = "LGPL"
__version__ = "0.5.0"
__maintainer__ = "Daniele Salvatore Schiera"
__email__ = "daniele.schiera@polito.it"
__status__ = "Development"

DATE_FORMAT = "YYYY-MM-DD HH:mm:ss"
CALC_MODELS = ['pvgis_hourly']

PVGIS_HOURLY_CONFIGS = {
    "latitude": 45,
    "longitude": 7.68,
    "start": 2019,
    "end": 2019,
    "peakpower": 1,
    "surface_tilt": 25,
    "surface_azimuth": 0,
    "pvtechchoice": 'crystSi',
    "components": False,
    "usehorizon": True,
    "pvcalculation": True,
    "mountingplace": 'building',
    "trackingtype": 0,
    "loss": 14,
    "optimal_surface_tilt": False,
    "optimalangles": False,
    "url": 'https://re.jrc.ec.europa.eu/api/v5_2/',
    "map_variables": True,
    "timeout": 30,
    "raddatabase": 'PVGIS-SARAH2'}


class PVSystem():
    def __init__(self, start_date="2020-01-01 00:00:00", calc_model="pvgis_hourly", **configs):
        self.start_date = pd.to_datetime(start_date)
        self.start_year = self.start_date.year

        if calc_model not in CALC_MODELS:
            raise ValueError(f'The calculation model must be one of the following: {CALC_MODELS}')
        self.calc_model = calc_model

        self.set_configuration(**configs)

    def set_configuration(self, **configs):
        if self.calc_model == 'pvgis_hourly':
            self.__dict__.update(PVGIS_HOURLY_CONFIGS)
            if self.start_year >= 2005 and self.start_year <= 2020: # for PVGIS-SARAH2
                self.start = self.start_year
                self.end = self.start_year
            self.__dict__.update(**configs)
            self.pvgis_params = {x: getattr(self, x) for x in PVGIS_HOURLY_CONFIGS.keys()}

    def _check_params_required(self, kwargdict, requiredargs):
        for r in requiredargs:
            assert r in kwargdict.keys()


    def get_power_pvgis(self):

        ts, metadata, inputs = get_pvgis_hourly(**self.pvgis_params)
        log.debug(metadata)
        log.debug(inputs)
        # 10 minutes correction
        ts = ts.resample(pd.Timedelta(10 * 60, unit='seconds')).interpolate().resample('H').interpolate().fillna(0)
        # Change year
        if self.start_year != self.start:
            ts.index = pd.to_datetime(ts.index, utc=True) + pd.offsets.DateOffset(years=self.start_year - ts.index[0].year)

        return ts



if __name__ == "__main__":

    pv = PVSystem(start_date="2020-01-01 00:00:00", latitude=38.11,longitude=13.352, optimalangles=True)
    ts = pv.get_power_pvgis()