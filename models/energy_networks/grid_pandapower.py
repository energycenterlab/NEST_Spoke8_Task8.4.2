"""
Pandapower Simulator
"""

import json
import math
import os.path

import pandas as pd
import pandapower as pp
from pandapower.timeseries import DFData
from pandapower.timeseries import OutputWriter
from pandapower.control import ConstControl
from pandapower.timeseries.run_time_series import run_timeseries, run_time_step, init_time_series
import pandapower.networks as ppn


OUTPUT_ATTRS = {
    'Bus': ['p_mw', 'q_mvar', 'vm_pu', 'va_degree'],
    'Load': ['p_mw', 'q_mvar'],
    'Sgen': ['p_mw', 'q_mvar'],
    'Trafo': ['va_lv_degree', 'loading_percent'],
    'Line': ['i_ka', 'loading_percent'],
    'Ext_grid': ['p_mw', 'q_mvar'],
}


class PandapowerSim(object):

    def __init__(self):
        self.entity_map = {}

    def load_case(self, path, grid_idx):
        """
        Loads a pandapower network, the network should be ready in a separate json or excel file or as stated above
        TODO: pypower converter and network building with only parameter as input
        """
        loaders = {
            '.json': 1,
            '.xlsx': 2,
            '': 3
        }
        try:
            ext = os.path.splitext(path)[-1]
            loader = loaders[ext]
        except KeyError:
            raise ValueError("Don't know how to open '%s'" % path)

        if loader == 1:
            self.net = pp.from_json(path)
        elif loader == 2:
            self.net = pp.from_excel(path)
        else:
            if path == 'cigre_hv':
                self.net = ppn.create_cigre_network_hv()
            elif path == 'cigre_mv_all':
                self.net = ppn.create_cigre_network_mv(with_der='all')
            elif path == 'cigre_mv_pv_wind':
                self.net = ppn.create_cigre_network_mv(with_der='pv_wind')
            elif path == 'cigre_lv':
                self.net = ppn.create_cigre_network_lv()
            elif path == 'lv_4b_pv':
                self.net = ppn.simple_four_bus_system()
            elif path == 'lv_10b_4l':
                self.net = ppn.four_loads_with_branches_out()

            # TODO correggere l'import di simbench
            # try:
            #     import simbench as sb
            #     self.net = sb.get_simbench_net(path)
            # except:
            #     raise ImportError(
            #         'Loading of simbench grid was not possible. If you want to use a simbench grid, you have to
            #         install simbench with "pip install simbench".')

        self.bus_id = self.net.bus.name.to_dict()

        # create virtual loads and gens on each bus ready to be plugged in
        pp.create_sgens(self.net, self.net.bus.index,0.0, name=[f'ext_sgen_at_{self.net.bus.name[i]}' for i in self.net.bus.name.to_dict()])
        pp.create_loads(self.net, self.net.bus.index,0.0, name=[f'ext_load_at_{self.net.bus.name[i]}' for i in self.net.bus.name.to_dict()])
        # =======================================================================

        # # create elements indices, to create entities
        # self.load_id = self.net.load.name.to_dict()
        # self.sgen_id = self.net.sgen.name.to_dict()
        # self.line_id = self.net.line.name.to_dict()
        # self.trafo_id = self.net.trafo.name.to_dict()
        # self.switch_id = self.net.switch.name.to_dict()
        # self.storage_id = self.net.storage.name.to_dict()
        #
        # # load the entity map
        # self._get_slack(grid_idx)
        # self._get_buses(grid_idx)
        # self._get_lines(grid_idx)
        # self._get_trafos(grid_idx)
        # self._get_loads(grid_idx)
        # self._get_sgen(grid_idx)
        # self._get_storage(grid_idx)

        # entity_map = self.entity_map
        ppc = self.net  # pandapower case


        if 'profiles' in self.net:
            time_steps = range(0, len(self.net.profiles['load']))
            output_dir = os.path.join(os.getcwd(), "time_series_example")
            ow = create_output_writer(self.net, time_steps,
                                      output_dir)  # just created to update res_bus in each time step
            self.ts_variables = init_time_series(self.net, time_steps)
        else:
            pass

        return ppc #entity_map

    def _get_slack(self, grid_idx):
        """Create entity of the slack bus"""

        self.slack_bus_idx = self.net.ext_grid.bus[0]
        bid = self.bus_id[self.slack_bus_idx]
        eid = make_eid(bid, grid_idx)

        self.entity_map[eid] = {
            'etype': 'Ext_grid',
            'idx': self.slack_bus_idx,
            'static': {'vm_pu': self.net.ext_grid['vm_pu'],
                       'va_degree': self.net.ext_grid['va_degree']
                       }
        }
        slack = (0, self.slack_bus_idx)

        return slack

    def _get_buses(self, grid_idx):
        """Create entities of the buses"""
        buses = []

        for idx in self.bus_id:
            if self.slack_bus_idx != idx:
                element = self.net.bus.iloc[idx]
                bid = element['name']
                eid = make_eid(bid, grid_idx)
                buses.append((idx, element['vn_kv']))
                self.entity_map[eid] = {
                    'etype': 'Bus',
                    'idx': idx,
                    'static': {
                        'vn_kv': element['vn_kv']
                    },
                }
            else:
                pass

        return buses

    def _get_loads(self, grid_idx):
        """Create load entities"""
        loads = []
        id_list = list(self.load_id.values())
        id_count = {i: id_list.count(i) for i in id_list}
        # Migliroamento id
        for idx in self.load_id:
            element = self.net.load.iloc[idx]
            if id_count[element['name']]==1:
                eid = make_eid(element['name'], grid_idx)
            else:
                eid = f"{make_eid(element['name'], grid_idx)}{id_count[element['name']]}"
                id_count[element['name']] -= 1

            bid = make_eid(self.bus_id[element['bus']], grid_idx)

            element_data = element.to_dict()
            keys_to_del = ['name', 'const_z_percent', 'const_i_percent', 'min_q_mvar', 'min_p_mw', 'max_q_mvar',
                           'max_p_mw']  # TODO non per forza da eliminare ma utili per OPF
            element_data_static = {key: element_data[key] for key in element_data if key not in keys_to_del}

            # time series calculation
            if 'profile' in element_data_static:
                if type(element_data_static['profile']) != float:
                    profile_name = element_data_static['profile']

                    datasource = pd.DataFrame()
                    datasource[profile_name + '_pload'] = self.net.profiles['load'][profile_name + '_pload'] * \
                                                          element['p_mw']
                    datasource[profile_name + '_qload'] = self.net.profiles['load'][profile_name + '_qload'] * \
                                                          element['q_mvar']

                    ds = DFData(datasource)

                    ConstControl(self.net, element='load', variable='p_mw', element_index=idx,
                                 data_source=ds, profile_name=profile_name + '_pload')

                    ConstControl(self.net, element='load', variable='q_mvar', element_index=idx,
                                 data_source=ds, profile_name=profile_name + '_qload')
            self.entity_map[eid] = {'etype': 'Load', 'idx': idx, 'static': element_data_static, 'related': [bid]}

            loads.append((bid, element['p_mw'], element['q_mvar'], element['scaling'], element['in_service']))

        return loads

    def _get_storage(self, grid_idx):
        """
        Create storage entities
        :param grid_idx: int with the grid ID
        """
        storages = []

        for idx in self.storage_id:

            # TODO check the correct indexing
            element = self.net.storage.iloc[idx]
            eid = make_eid(element['name'], grid_idx)
            bid = make_eid(self.bus_id[element['bus']], grid_idx)

            element_data = element.to_dict()
            keys_to_del = ['name', 'min_q_mvar',
                           'min_p_mw', 'max_q_mvar', 'max_p_mw']
            element_data_static = {
                key: element_data[key] for key in element_data if key not in keys_to_del}

            # time series calculation
            if 'profile' in element_data_static:
                if type(element_data_static['profile']) != float:
                    profile_name = element_data_static['profile']

                    datasource = pd.DataFrame()
                    datasource[profile_name + '_pload'] = self.net.profiles['storage'][profile_name +
                                                                                       '_psto'] * element['p_mw']

                    ds = DFData(datasource)

                    ConstControl(
                            self.net,
                            element='storage',
                            variable='p_mw',
                            element_index=idx,
                            data_source=ds,
                            profile_name=profile_name +
                                         '_psto')

            self.entity_map[eid] = {
                'etype': 'Storage',
                'idx': idx,
                'static': element_data_static,
                'related': [bid]}

            storages.append((
                bid,
                element['p_mw'],
                element['q_mvar'],
                element['scaling'],
                element['in_service'],
                element['soc_percent']
            ))

        return storages

    def _get_sgen(self, grid_idx):
        """Create static generator entities"""
        sgens = []

        for idx in self.sgen_id:
            element = self.net.sgen.iloc[idx]
            eid = make_eid(element['name'], grid_idx)
            bid = make_eid(self.bus_id[element['bus']], grid_idx)

            element_data = element.to_dict()
            keys_to_del = ['name', 'min_q_mvar', 'min_p_mw', 'max_q_mvar', 'max_p_mw']
            element_data_static = {key: element_data[key] for key in element_data if key not in keys_to_del}

            # time series calculation
            if 'profile' in element_data_static:
                if type(element_data_static['profile']) != float:
                    profile_name = element_data_static['profile']

                    datasource = pd.DataFrame()
                    datasource[profile_name] = self.net.profiles['renewables'][profile_name] * element['p_mw']

                    ds = DFData(datasource)

                    ConstControl(self.net, element='sgen', variable='p_mw', element_index=idx,
                                 data_source=ds, profile_name=profile_name)

            self.entity_map[eid] = {'etype': 'Sgen', 'idx': idx, 'static': element_data_static, 'related': [bid]}

            sgens.append((bid, element['p_mw'], element['q_mvar'], element['scaling'], element['in_service']))

        return sgens

    def _get_lines(self, grid_idx):
        """create branches entities"""
        lines = []

        for idx in self.line_id:
            element = self.net.line.iloc[idx]
            eid = make_eid(element['name'], grid_idx)
            fbus = make_eid(self.bus_id[element['from_bus']], grid_idx)
            tbus = make_eid(self.bus_id[element['to_bus']], grid_idx)

            f_idx = self.entity_map[fbus]['idx']
            t_idx = self.entity_map[tbus]['idx']

            element_data = element.to_dict()
            keys_to_del = ['name', 'from_bus', 'to_bus']
            element_data_static = {key: element_data[key] for key in element_data if key not in keys_to_del}
            # del element_data_static

            self.entity_map[eid] = {'etype': 'Line', 'idx': idx, 'static': element_data_static,
                                    'related': [fbus, tbus]}

            lines.append((f_idx, t_idx, element['length_km'], element['r_ohm_per_km'], element['x_ohm_per_km'],
                          element['c_nf_per_km'], element['max_i_ka'], element['in_service']))

        return lines

    def _get_trafos(self, grid_idx):
        """Create trafo entities"""
        trafos = []

        for idx in self.trafo_id:
            element = self.net.trafo.iloc[idx]
            eid = make_eid(element['name'], grid_idx)
            hv_bus = make_eid(self.bus_id[element['hv_bus']], grid_idx)
            lv_bus = make_eid(self.bus_id[element['lv_bus']], grid_idx)

            hv_idx = self.entity_map[hv_bus]['idx']
            lv_idx = self.entity_map[lv_bus]['idx']

            element_data = element.to_dict()
            keys_to_del = ['name', 'hv_bus', 'lv_bus']
            element_data_static = {key: element_data[key] for key in element_data if key not in keys_to_del}
            # del element_data_static

            self.entity_map[eid] = {'etype': 'Trafo', 'idx': idx, 'static': element_data_static,
                                    'related': [hv_bus, lv_bus]}

        trafos.append((hv_idx, lv_idx, element['sn_mva'], element['vn_hv_kv'], element['vn_lv_kv'],
                       element['vk_percent'], element['vkr_percent'], element['pfe_kw'], element['i0_percent'],
                       element['shift_degree'], element['tap_side'], element['tap_pos'], element['tap_neutral'],
                       element['tap_min'], element['tap_max'], element['in_service']))

        return trafos

    def set_inputs(self, etype, idx, data, static):
        """setting the input from other simulators"""
        for name, value in data.items():

            if etype in ['Load', 'Storage', 'Sgen']:
                elements = getattr(self.net, etype.lower())
                elements.at[idx, name] = value

            elif etype == 'Trafo':
                if 'tap_turn' in data:
                    tap = 1 / static['tap_pos'][data['tap_turn']]
                    self.net.trafo.at[idx, 'tap_pos'] = tap  # TODO: access number of trafos

            else:
                raise ValueError('etype %s unknown' % etype)

    def powerflow(self):
        """Conduct power flow"""
        pp.runpp(self.net, numba=False)

    def powerflow_timeseries(self, time_step):
        """Conduct power flow series"""

        run_time_step(self.net, time_step, self.ts_variables, _ppc=True, is_elements=True)

    def get_cache_entries(self):
        """cache the results of the power flow to be communicated to other simulators"""

        cache = {}
        case = self.net

        for eid, attrs in self.entity_map.items():
            etype = attrs['etype']
            idx = attrs['idx']
            data = {}
            attributes = OUTPUT_ATTRS[etype]

            if not case.res_bus.empty:
                element_name = f'res_{etype.lower()}'
                if etype != 'Ext_grid':
                    element = getattr(case, element_name).iloc[idx]
                else:
                    element = getattr(case, element_name)

                for attr in attributes:
                    data[attr] = element[attr]

            else:
                # Failed to converge.
                for attr in attributes:
                    data[attr] = float('nan')

            cache[eid] = data
        return cache


def make_eid(name, grid_idx):
    return '%s-%s' % (grid_idx, name)


def create_output_writer(net, time_steps, output_dir):
    """Pandapower output to save results"""
    ow = OutputWriter(net, time_steps, output_path=output_dir, output_file_type=".xls")
    # these variables are saved to the harddisk after / during the time series loop
    for etype, attrs in OUTPUT_ATTRS.items():
        element_name = f'res_{etype.lower()}'
        for attr in attrs:
            ow.log_variable(element_name, attr)

    return ow


if __name__ == "__main__":
    import pandapower.plotting as pt


    ppc = pandapower()
    x, y = ppc.load_case('lv_10b_4l', 0)  # ('cigre_hv',0)#('lv_4b_pv', 0)
    buss = ppc._get_buses(0)
    stoxx = ppc._get_storage(0)

    ppc.powerflow()
    # busx=ppc._get_loads()
    # busxx = ppc._get_loads(0)
    # busy=ppc._get_branches()
    # buso=ppc._get_trafos()
    # busz=ppc._get_sgen()
    # ppc.entity_map()
    res = ppc.get_cache_entries()

    # pt.simple_plot(ppc.net)
    # line_trace = pt.plotly.create_line_trace(ppc.net)
    # bus_trace = pt.plotly.create_bus_trace(ppc.net)
    # trafo_trace = pt.plotly.create_trafo_trace(ppc.net)

    pt.plotly.simple_plotly(ppc.net, figsize=2, aspectratio=(1, 2))

    pt.plotly.pf_res_plotly(ppc.net, figsize=2, aspectratio=(1, 2))

    ppc.net.load.at[10, 'in_service'] = True
    ppc.net.load.at[10, 'p_mw'] = 0.08

    ppc.net.load.at[11, 'in_service'] = True
    ppc.net.load.at[11, 'p_mw'] = 0.08

    ppc.net.load.at[12, 'in_service'] = True
    ppc.net.load.at[12, 'p_mw'] = 0.08

    ppc.powerflow()

    pt.plotly.pf_res_plotly(ppc.net, figsize=2, aspectratio=(1, 2))
