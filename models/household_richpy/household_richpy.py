"""
A richardsonpy standalone simulator version to be stepped

https://github.com/RWTH-EBC/richardsonpy
"""
import pandas as pd
import richardsonpy.classes.occupancy as occ
import richardsonpy.functions.change_resolution as cr
import richardsonpy.functions.load_radiation as loadrad
import models.household_richpy.classes.electric_load as eload

__author__ = "Daniele Salvatore Schiera"
__credits__ = ["Daniele Salvatore Schiera"]
__license__ = "LGPL"
__version__ = "0.5.0"
__maintainer__ = "Daniele Salvatore Schiera"
__email__ = "daniele.schiera@polito.it"
__status__ = "Development"

DATE_FORMAT = 'YYYY-MM-DD HH:mm:ss'

class HouseholdSim():
    def __init__(self, nb_occ=3, annual_demand=None, timestep=3600, start_date='2020-01-01', stop_date='2020-01-01', stepped=False):
        self.nb_occ = nb_occ
        self.timestep = timestep  # in seconds, default 3600 seconds
        self.annual_demand = annual_demand
        self.stepped = stepped
        self.stop_date = pd.to_datetime(stop_date) + pd.Timedelta(1, unit='day')
        self.start_date = pd.to_datetime(start_date)
        self.dt_index = pd.date_range(self.start_date,self.stop_date,freq=pd.Timedelta(self.timestep, unit='seconds'),closed='left')
        self.start_time = self.start_date.dayofyear
        self.stop_time = self.stop_date.dayofyear - 1
        self.initial_day = self.start_date.dayofweek+1


        # Todo q_direct e q_diffuse da fornire dall'esterno, da file meteo
        self.q_direct, self.q_diffuse = loadrad.get_rad_from_try_path()  # for lighting usage
        self.q_direct = cr.change_resolution(self.q_direct, old_res=3600, new_res=self.timestep)
        self.q_diffuse = cr.change_resolution(self.q_diffuse, old_res=3600, new_res=self.timestep)

    def run(self):
        self.occ_gen = occ.Occupancy(number_occupants=self.nb_occ,nb_days=self.stop_time)  # for el. load gen
        self.occupancy = cr.change_resolution(self.occ_gen.occupancy, old_res=600, new_res=self.timestep)
        self.el_load_gen = eload.ElectricLoad(occ_profile=self.occ_gen.occupancy,
                                              total_nb_occ=self.nb_occ,
                                              q_direct=self.q_direct,
                                              q_diffuse=self.q_diffuse,
                                              timestep=self.timestep,
                                              annual_demand=self.annual_demand, is_sfh=True,
                                              path_app=None, path_light=None, randomize_appliances=True,
                                              prev_heat_dev=False, light_config=0,
                                              initial_day=self.initial_day,
                                              season_light_mod=False,
                                              light_mod_fac=0.25, do_normalization=False, calc_profile=True,
                                              save_app_light=False, stop_time=self.stop_time, stepped=self.stepped)

        self.res = pd.DataFrame({'totload': self.el_load_gen.loadcurve, 'occ':self.occupancy},index=self.dt_index)

        return self.res


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    hh = HouseholdSim(start_date= '2015-01-01 00:00:00', stop_date='2015-01-05 00:00:00')
    ori = hh.run()

