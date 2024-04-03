"""
PV simulator API for mosaik based on pvlib
"""
import warnings
import mosaik_api_v3
import pandas as pd

__author__ = "Daniele Salvatore Schiera"
__credits__ = ["Daniele Salvatore Schiera"]
__license__ = "LGPL"
__version__ = "0.5.0"
__maintainer__ = "Daniele Salvatore Schiera"
__email__ = "daniele.schiera@polito.it"
__status__ = "Development"

import sys
from pathlib import Path
PROJECT_ROOT = str(Path(__file__).resolve().parents[2]).replace('\\', '/')
sys.path.append(PROJECT_ROOT)
from models.pvsim_pvlib import pvsim_pvlib

warnings.filterwarnings("ignore", category=FutureWarning)
META = {
    "api_version": "3.0",
    'type': 'time-based',
    'models': {}
}


class PVSim(mosaik_api_v3.Simulator):
    def __init__(self):
        super().__init__(META)
        self.eid_prefix = ''
        self.entities = {}
        self.sid = None

        self.simulator = pvsim_pvlib.PVSystem

    def init(self, sid, time_resolution=1., eid_prefix=None, timestep=3600, start_date='2020-01-01 00:00:00',
             stop_date='2020-01-07', days=None,calc_model='pvgis_hourly', sim_meta=None):
        self.sid = sid
        self.time_resolution = time_resolution
        self.timestep = timestep
        self.start_date = start_date
        self.calc_model = calc_model
        if days:
            self.stop_date = str(pd.to_datetime(self.start_date) + pd.Timedelta(days, unit='day'))
        else:
            self.stop_date = stop_date
        self.cache = {}
        if eid_prefix is not None:
            self.eid_prefix = eid_prefix

        if self.meta['models'] == {}:
            self.meta['models'] = sim_meta
        return self.meta

    def create(self, num, model,
               latitude=45,
               longitude=7.68,
               peakpower=1,
               surface_tilt=25,
               surface_azimuth=0, **kwargs):
        next_eid = len(self.entities)
        entities = []

        for i in range(next_eid, next_eid + num):
            eid = '%s_%d' % (model, i)
            # fid = self.sid +'.'+eid # full_id
            res = self.simulator(calc_model=self.calc_model, start_date=self.start_date,
                                                latitude=latitude,
                                                longitude=longitude,
                                                peakpower=peakpower,
                                                surface_tilt=surface_tilt,
                                                surface_azimuth=surface_azimuth, **kwargs).get_power_pvgis()
            sim_timestep = int((res.index[1]-res.index[0]).total_seconds())
            if self.timestep*self.time_resolution < sim_timestep: # resampling
                res = res.resample(pd.Timedelta(self.timestep*self.time_resolution, unit='seconds')).interpolate()
            self.entities[eid] = res
            entities.append({"eid": eid, "type": model, "rel": []})
        return entities

    def step(self, time, inputs, max_advance):
        expected_date = pd.to_datetime(self.start_date) + pd.Timedelta(seconds=time * self.time_resolution)

        for eid, pv in self.entities.items():

            if expected_date not in pv.index:
                raise IndexError(f'Wrong date, expected "{expected_date}"')

            self.cache[eid] = pv.loc[expected_date]

        return time + int(self.timestep)

    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            if eid not in self.entities.keys():
                raise ValueError('Unknown entity ID "%s"' % eid)
            model_type = eid.split('_')[0]

            data[eid] = {}
            for attr in attrs:
                if attr not in self.meta['models'][model_type]['attrs']:
                    raise ValueError('Unknown output attribute: %s' % attr)
                data[eid][attr] = self.cache[eid][attr]

        return data


if __name__ == '__main__':
    mosaik_api_v3.start_simulation(PVSim())
