"""
Household Load and Occupancy Simulator API for Mosaik.
Based on richardsonpy
"""

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
from models.household_richpy import household_richpy

META = {
    "api_version": "3.0",
    'type': 'time-based',
    'models': {}
}


class HouseholdRich(mosaik_api_v3.Simulator):
    def __init__(self):
        super().__init__(META)
        self.eid_prefix = ''
        self.entities = {}
        self.sid = None

        self.simulator = household_richpy.HouseholdSim

    def init(self, sid, time_resolution=1., eid_prefix=None, timestep=3600, start_date='2020-01-01',
             stop_date='2020-01-07', days=None, stepped=False, sim_meta=None):
        self.sid = sid
        self.time_resolution = time_resolution
        self.timestep = timestep
        self.start_date = start_date
        if days:
            self.stop_date = str(pd.to_datetime(self.start_date) + pd.Timedelta(days, unit='day'))
        else:
            self.stop_date = stop_date
        self.stepped = stepped
        self.current_date = self.start_date
        self.cache = {}
        if eid_prefix is not None:
            self.eid_prefix = eid_prefix

        if self.meta['models'] == {}:
            self.meta['models'] = sim_meta
        return self.meta

    def create(self, num, model, nb_occ=3, annual_demand=None):
        next_eid = len(self.entities)
        entities = []

        for i in range(next_eid, next_eid + num):
            eid = '%s_%d' % (model, i)
            # fid = self.sid +'.'+eid # full_id
            self.entities[eid] = self.simulator(start_date=self.start_date, stop_date=self.stop_date,timestep=self.timestep).run()

            entities.append({"eid": eid, "type": model, "rel": []})
        return entities

    def step(self, time, inputs, max_advance):
        expected_date = pd.to_datetime(self.start_date) + pd.Timedelta(seconds=time * self.time_resolution)

        for eid, hh in self.entities.items():

            if expected_date not in hh.index:
                raise IndexError(f'Wrong date, expected "{expected_date}"')

            self.cache[eid] = hh.loc[expected_date]

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
    mosaik_api_v3.start_simulation(HouseholdRich())
