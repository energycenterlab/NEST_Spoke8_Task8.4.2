#!/usr/bin/env python
"""
Co-simulation & Optimization for Energy Systems Integration (COESI).

Tool-chain to perform simulation and optimization of urban energy scenarios and use cases, based on co-simulation
and FunctionalMock-up Interface through Mosaik engine implementation.

CLI for running scenario.

Research group of Politecnico di Torino Energy Center Lab.
"""
import argparse
from dataclasses import dataclass, field, asdict
from datetime import *
from typing import get_origin, List, Dict, Any, Union, Optional, Literal

import mosaik
from mosaik import util as mosaik_util
from loguru import logger

__author__ = "Daniele Salvatore Schiera"
__credits__ = ["Daniele Salvatore Schiera, Pietro Rando Mazzarino"]
__license__ = "LGPL"
__version__ = "0.1.0"
__maintainer__ = "Daniele Salvatore Schiera"
__email__ = "daniele.schiera@polito.it"
__status__ = "Development"

# from src.utilities.villas import villas_pb2 # todo update villas
from definitions import *
from utils import *


class Scenario:
    def __init__(self, filename, scenario_dir=SCENARIO_ROOT, webdash=False, realtime=False, debug=False, **mk_params):
        self.models_instances = None
        self.simulators_instances = None
        self.world = None
        self.webdash = webdash
        self.realtime = realtime
        self.scenario_dir = scenario_dir
        self.scenario_filename = filename
        self.debug = debug
        self.mk_params = mk_params
        # Mosaik Scenario Params {rt_strict:False, lazy_stepping:False}
        # lazy stepping False fa proseguire i sim allo steps fin dove richiesto, piu memoria ma piu veloce.

        self.scenario_data = ScenarioData(**self.load_config_yaml(self.scenario_filename, self.scenario_dir))

        self.scenario_cfg = self.scenario_data.SCEN_CONFIG
        self.simulators_cfg = self.scenario_data.simulators
        self.connections_cfg = self.scenario_data.CONNECTIONS
        self.data_collector_cfg = self.scenario_data.SCEN_OUTPUTS

        self.scenario_name = self.scenario_cfg.SCENARIO_NAME

        if self.data_collector_cfg != {}:
            self.set_data_collector()

        self.set_simulators_cfg()

    def run(self):
        self.start_environment()
        self.create_simulators()
        self.create_models()
        self.connect_models()
        self._save_scenario_complete()
        if self.realtime == False:
            run = input('Run Simulation? y/N')
            if run == 'y':
                sim_start_time = datetime.now()
                self.world.run(until=self.scenario_cfg.stop_time, rt_factor=self.scenario_cfg.RT_FACTOR,
                               **self.mk_params)  # rtfactor = 1 => 1 simulation time unit == takes 1 second
                delta_sim_time = datetime.now() - sim_start_time
                logger.info(f'Simulation took {delta_sim_time}')
            else:
                sys.exit(1)
        elif self.realtime == True:  # todo generalization required
            localIP = ''  # here the local IP
            localPort = 13000  # here local port
            bufferSize = 1024

            UDPServerSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
            UDPServerSocket.bind((localIP, localPort))

            logger.info("UDP server up and listening")
            start = False
            msg = villas_pb2.Message()
            logger.info("Waiting")
            while (not start):
                payload = UDPServerSocket.recv(bufferSize)
                logger.info(payload)
                msg.ParseFromString(payload)
                STOP_TIME = msg.samples[0].values[0].f
                start = True
                UDPServerSocket.close()

            sim_start_time = datetime.now()
            logger.info(STOP_TIME)
            self.world.run(until=int(STOP_TIME), rt_factor=self.scenario_cfg.RT_FACTOR,
                           **self.mk_params)
            delta_sim_time = datetime.now() - sim_start_time
            logger.info(f'\nSimulation took {delta_sim_time}')

    def load_config_yaml(self, config, dir):
        config = config + '.yaml'
        self.src_cfg = os.path.join(dir, config).replace('\\', '/')
        if dir == SCENARIO_ROOT:
            self.src_cfg = os.path.join(dir, config)
            if os.path.isfile(self.src_cfg):
                with open(self.src_cfg, 'r') as stream:
                    try:
                        dict_object = yaml.safe_load(stream)
                    except yaml.YAMLError as exc:
                        raise Exception(exc)
            else:
                raise FileExistsError(
                    f'File YAML with name "{self.src_cfg.split()[0]}" does not exist in the input data '
                    f'directory!')
            Path(TEMP_ROOT).mkdir(parents=True, exist_ok=True)
            shutil.copy(self.src_cfg, TEMP_ROOT, follow_symlinks=True)
            src_cfg_dest_old = os.path.join(TEMP_ROOT, config)
            src_cfg_dest_new = os.path.join(TEMP_ROOT, f'temp_scn.yaml')  # temp scenario
            if os.path.exists(src_cfg_dest_new):
                os.remove(src_cfg_dest_new)
            os.rename(src_cfg_dest_old, src_cfg_dest_new)
            return dict_object
        else:  # for other roots like SOURCE_ROOT and parent folders
            if os.path.isfile(self.src_cfg):
                with open(self.src_cfg, 'r') as stream:
                    try:
                        dict_object = yaml.safe_load(stream)
                    except yaml.YAMLError as exc:
                        raise Exception(exc)
            else:
                raise FileExistsError(
                    f'File YAML with name "{self.src_cfg.split()[0]}" does not exist in the input data '
                    f'directory!')
            return dict_object

    def _save_scenario_complete(self):
        self.scenario_complete = {'SCEN_CONFIG': {**asdict(self.scenario_cfg)},
                                  'SIM_CONFIG': {**{x: asdict(y) for x, y in self.simulators_cfg.items()}},
                                  'CONNECTIONS': {**self.connections_cfg},
                                  'SCEN_OUTPUTS':{**self.data_collector_cfg}}

        Path(TEMP_ROOT).mkdir(parents=True, exist_ok=True)
        temp_scn_path = os.path.join(TEMP_ROOT, f'temp_scn.yaml')
        with open(temp_scn_path, 'w') as outfile:
            yaml.dump(self.scenario_complete, outfile, default_flow_style=False)

    def set_data_collector(self):
        for key, values in self.data_collector_cfg.items():
            if key == 'ZMQ':
                sim_data = self.load_config_yaml('webapp_config', RESOURCE_ROOT + '/sim_templates')[key]
                self.simulators_cfg[key] = SimulatorData(simulator_name=key, **sim_data)
                self.simulators_cfg[key].PARAMS['step_size'] = values['step_size']
                self.simulators_cfg[key].PARAMS['duration'] = self.scenario_cfg.stop_time
            # DB setup
            if key == 'DB':
                sim_data = self.load_config_yaml('db_hdf5_config', RESOURCE_ROOT + '/templates')[key]
                self.simulators_cfg[key] = SimulatorData(simulator_name=key, **sim_data)
                self.simulators_cfg[key].PARAMS['step_size'] = values['step_size']
                self.simulators_cfg[key].PARAMS['duration'] = self.scenario_cfg.stop_time
                self.simulators_cfg[key].sim_models['db'].PARAMS['filename'] = self.scenario_cfg.SCENARIO_NAME
            if key == 'INFLUXDB':
                sim_data = self.load_config_yaml('db_influxdb_config', RESOURCE_ROOT + '/templates')[key]
                self.simulators_cfg[key] = SimulatorData(simulator_name=key, **sim_data)
                self.simulators_cfg[key].PARAMS['step_size'] = values['step_size']
                self.simulators_cfg[key].sim_models['db'].PARAMS['filename'] = self.scenario_cfg.SCENARIO_NAME

    def set_simulators_cfg(self):
        for sim, cfg in self.simulators_cfg.items():
            if 'start_date' in cfg.PARAMS:  # todo è possibile fare questa operazione con le dataclass ereditando la classe dato scenarioset con python 3.10 e kw_only=True
                if cfg.PARAMS['start_date'] == 'START_DATE':
                    cfg.PARAMS['start_date'] = self.scenario_cfg.START_DATE
            if 'days' in cfg.PARAMS:
                if cfg.PARAMS['days'] == 'DAYS':
                    cfg.PARAMS['days'] = self.scenario_cfg.DAYS

    def start_environment(self):
        ## Mosaik setup
        mk_config = {
            'addr': ('127.0.0.1', 5555),
            'start_timeout': 30,  # seconds default 10
            'stop_timeout': 30,  # seconds default 10
        }
        SIM_CONFIG = {x: y.RUN_PROCESS for x, y in self.simulators_cfg.items()}
        #logger.debug(SIM_CONFIG)
        logger.info('Creating environment..')
        self.world = mosaik.World(sim_config=SIM_CONFIG, mosaik_config=mk_config,
                                  time_resolution=self.scenario_cfg.time_resolution, debug=self.debug)
        logger.info('Done')

    def create_simulators(self):
        logger.info('Starting simulators..')
        self.simulators_instances = {}
        for sim, cfg_sim in self.simulators_cfg.items():
            sim_meta = {}
            for model, cfg_model in cfg_sim.sim_models.items():  # Todo recuperare da template per i model_meta
                params_names = list(cfg_model.PARAMS.keys())
                # if isinstance(cfg_model.PARAMS,dict):
                #     params_names = list(cfg_model.PARAMS.keys())
                # else:
                #     params_names = []
                sim_meta[model] = {key.lower(): value for key, value in asdict(cfg_model).items()}
                del sim_meta[model]['model_name']  # todo migliorare
                sim_meta[model]['params'] = params_names
                sim_meta[model]['non-persistent'] = sim_meta[model].pop("non_persistent")
            params = {key.lower(): value for key, value in cfg_sim.PARAMS.items()}
            self.simulators_instances[sim] = self.world.start(sim, sim_meta=sim_meta, **params)
            if 'solver' in cfg_sim.PARAMS.keys():
                getattr(self.simulators_instances[sim], "solver_call")(cfg_sim.PARAMS['solver'])
        logger.info('Done')

    def create_models(self):
        logger.info('Creating model instances..')
        self.models_instances = {}
        for sim, cfg_sim in self.simulators_cfg.items():
            self.models_instances[sim] = {}
            for model, cfg_model in cfg_sim.sim_models.items():
                # Todo recuperare, ed integrare eventuali parametri del modello di default da un file/dict "model_meta"
                if "num" in cfg_model.PARAMS.keys():  # num entities with same set of parameters
                    num = cfg_model.PARAMS['num']
                    del cfg_model.PARAMS['num']

                    entity = getattr(getattr(self.simulators_instances[sim], model), 'create')(num, **cfg_model.PARAMS)
                    for n in range(num):
                        self.models_instances[sim][entity[n].eid] = entity[n]
                else:
                    # Todo, stesso modello, diversi parametri
                    # are_all_lists = all(isinstance(value, list) for value in cfg_model.PARAMS.values())
                    # if are_all_lists:
                    #     list_of_params = []
                    #     for values in zip(*cfg_model.PARAMS.values()):
                    #         new_dict = dict(zip(cfg_model.PARAMS.keys(), values))
                    #         list_of_params.append(new_dict)
                    #     for params in list_of_params:
                    #         entity = getattr(self.simulators_instances[sim], model)(**params)
                    #         self.models_instances[sim][entity.eid] = entity
                    # elif True in [isinstance(value, list) for value in cfg_model.PARAMS.values()]:
                    #     raise Exception(f'The list of values must be with the same length. {cfg_model.PARAMS}')
                    # else:
                    #     entity = getattr(self.simulators_instances[sim], model)(**cfg_model.PARAMS)
                    #     self.models_instances[sim][entity.eid] = entity
                    entity = getattr(self.simulators_instances[sim], model)(**cfg_model.PARAMS)
                    self.models_instances[sim][entity.eid] = entity
        logger.info('Done')

    def connect_models(self):
        logger.info('Connecting models..')
        if self.connections_cfg is not None:
            # models connections
            for cn in self.connections_cfg.values():
                # attrs_pairs
                attrs_pairs = []
                for attr in cn['ATTRS']:
                    if isinstance(attr, list):
                        attrs_pairs.append(tuple(attr))
                    else:
                        attrs_pairs.append(attr)
                if 'PARAMS' not in cn.keys():
                    cn['PARAMS'] = {}


                if isinstance(cn['FROM'], list) and isinstance(cn['TO'], list):
                    # random
                    from_set = [self._entity_eid(entity, self.models_instances) for entity in cn['FROM']]
                    to_set = [self._entity_eid(entity, self.models_instances) for entity in cn['TO']]
                    mosaik_util.connect_randomly(self.world, from_set, to_set, *cn['ATTRS'], **cn['PARAMS'])
                elif isinstance(cn['FROM'], list) or isinstance(cn['TO'], list):
                    # many_to_one
                    if isinstance(cn['FROM'], list):
                        many = [self._entity_eid(entity, self.models_instances) for entity in cn['FROM']]
                        one = self._entity_eid(cn['TO'], self.models_instances)
                        mosaik_util.connect_many_to_one(self.world, many, one, *attrs_pairs, **cn['PARAMS'])
                        # one_to_many
                    elif isinstance(cn['TO'], list):
                        many = [self._entity_eid(entity, self.models_instances) for entity in cn['TO']]
                        one = self._entity_eid(cn['FROM'], self.models_instances)
                        for to in many:
                            self.world.connect(one, to, *cn['ATTRS'], **cn['PARAMS'])
                # one_to_one
                else:
                    fro = self._entity_eid(cn['FROM'], self.models_instances)
                    to = self._entity_eid(cn['TO'], self.models_instances)
                    self.world.connect(fro, to, *attrs_pairs, **cn['PARAMS'])

        # data collectors connections
        if self.data_collector_cfg != {}:
            for scn_out in self.data_collector_cfg.keys():
                sim_model = self.models_instances[scn_out][scn_out.lower()]
                for ent_attr in self.data_collector_cfg[scn_out]['attrs']:
                    ent_attr = ent_attr.split('.')
                    if len(ent_attr) == 3:
                        entity = '.'.join(ent_attr[:2])
                        self.world.connect(self._entity_eid(entity, self.models_instances),
                                           sim_model, ent_attr[2])
                    elif len(ent_attr) == 4:
                        entity = '.'.join(ent_attr[:3])
                        self.world.connect(self._entity_eid(entity, self.models_instances),
                                           sim_model, ent_attr[3])
                    else:
                        # todo non dovrebbe servire piu
                        # world.connect(getattr(entities[ent_attr[0]],"children")[int(ent_attr[1])],
                        #               entities[scn_out.lower()],
                        #               ent_attr[2])
                        # world.connect(
                        #     getattr(entities[ent_attr[0]], "children")[[a.eid for a in getattr(entities[ent_attr[
                        #         0]], "children")].index(ent_attr[1])],
                        #     entities[scn_out.lower()],
                        #     ent_attr[2])
                        pass
        logger.info('Done')

    def _entity_eid(self, entity, entities):
        if len(entity.split('.')) == 3:
            sim, model, child_name = entity.split('.') # sim: 'grid', model: 'Grid_0', child_name: 'ext_load_at_bus6'
            id_child = [getattr(i, 'eid') for i in getattr(entities[sim][model], 'children')].index(child_name)
            return getattr(entities[sim][model], 'children')[id_child]
        elif len(entity.split('.')) == 2:
            try:
                sim, model = entity.split('.')
            except ValueError as error:
                logger.info(f'{error}\n {entity}')
            return entities[sim][model]
        else:
            raise ValueError(f'Something is wrong with Entity {entity}')



def _check_type(self):
    for name, field_type in self.__annotations__.items():
        actual_value = self.__dict__[name]

        if hasattr(field_type, "__origin__"):
            origin_type = get_origin(field_type)
            if origin_type is list:
                inner_type = field_type.__args__[0]
                if not all(isinstance(item, inner_type) for item in actual_value):
                    current_type = type(actual_value)
                    raise TypeError(
                        f"The elements of the list field `{name}` are not of type `{inner_type}` but are `{current_type}`")
            elif origin_type is dict:
                key_type, value_type = field_type.__args__
                if not all(isinstance(k, key_type) and isinstance(v, value_type) for k, v in actual_value.items()):
                    current_type = type(actual_value)
                    raise TypeError(
                        f"The keys and values of the dictionary field `{name}` are not of the expected types but are `{current_type}`")
        elif not isinstance(actual_value, field_type):
            current_type = type(actual_value)
            raise TypeError(
                f"The field `{name}` was assigned by `{current_type}` instead of `{field_type}`")


@dataclass()
class ScenarioSetData:
    SCENARIO_NAME: str
    START_DATE: str  # 'YYY-MM-DD HH:MM:SS'
    DAYS: Union[int, float]
    RT_FACTOR: Union[int, float] = None
    time_resolution: Union[int, float] = 1

    stop_time: int = field(init=False)

    def __post_init__(self):
        self.stop_time = int((self.DAYS) * (60 * 60 * 24) / self.time_resolution)
        _check_type(self)


@dataclass()
class SimulatorData:
    simulator_name: str
    RUN_PROCESS: dict
    PARAMS: dict
    MODELS: dict
    TYPE: Literal["time-based", "event-based", "hybrid"] = "time-based"
    EXTRA_METHODS: Optional[dict] = None

    sim_models: dict = field(init=False)

    def __post_init__(self):
        self.sim_models = {}
        for model_name, model_data in self.MODELS.items():
            self.sim_models[model_name] = ModelData(model_name=model_name, **model_data)
        _check_type(self)
        if 'cwd' not in self.RUN_PROCESS:
            self.RUN_PROCESS['cwd'] = SIM_ROOT + '/'
        if 'python' in self.RUN_PROCESS:
            try:
                self.RUN_PROCESS['python'] = SIM_ROOT.split('/')[-1] + '.' + \
                                             mk_sims_api_config['mk_api'][self.RUN_PROCESS['python']][0]
            except KeyError as err:
                namesim = self.RUN_PROCESS['python']
                logger.debug(f'{err}. {namesim} simulator api not present.')
        elif 'cmd' in self.RUN_PROCESS:
            try:
                self.RUN_PROCESS['cmd'] = mk_sims_api_config['mk_api'][self.RUN_PROCESS['cmd']][1]
            except KeyError as err:
                namesim = self.RUN_PROCESS['cmd']
                logger.debug(f'{err}. {namesim} simulator api not present.')


@dataclass()
class ScenarioData:
    SCEN_CONFIG: dict
    SIM_CONFIG: dict
    CONNECTIONS: dict
    SCEN_OUTPUTS: dict

    simulators: dict = field(init=False)

    def __post_init__(self):
        self.simulators = {}
        for sim_name, sim_data in self.SIM_CONFIG.items():
            self.simulators[sim_name] = SimulatorData(simulator_name=sim_name, **sim_data)
        _check_type(self)
        self.SCEN_CONFIG = ScenarioSetData(**self.SCEN_CONFIG)


@dataclass()
class ModelData:
    model_name: str
    PARAMS: Union[Dict[str, dict], List[Any]]
    ATTRS: List[str] = field(default_factory=lambda: [])
    PUBLIC: bool = True
    ANY_INPUTS: bool = True
    TRIGGER: List[str] = field(default_factory=lambda: [])
    NON_PERSISTENT: List[str] = field(default_factory=lambda: [])

    def __post_init__(self):
        _check_type(self)
        if isinstance(self.PARAMS, list):
            self.PARAMS = {}


if __name__ == '__main__':
    import time

    logger.info('COESI started.')
    # Run the simulation.

    # Default settings
    scenario_default = 'scenario_demo'
    scenario_dir = SCENARIO_ROOT #+ '/simulators_tests'
    webdash = False
    RT = False

    parser = argparse.ArgumentParser(description='Command line interface for scenario simulation within COESI.')
    parser.add_argument('-s', '--scenario_name', type=str, help='Name of the scenario configuration yaml file. It must '
                                                                'be in scenarios directory',
                        default=scenario_default)
    parser.add_argument('-sdir', '--scenario_dir', type=str, help='Name of the scenarios directory',
                        default=scenario_dir)
    parser.add_argument('-w', '--webdash', type=bool, default=webdash, help='Run the webdash. Default deactivated.')
    parser.add_argument('-rt', '--real_time', type=bool, default=RT, help='Run the RT simulation with Opal-RT. '
                                                                          'Default deactivated.')

    args = parser.parse_args()
    if len(sys.argv) < 2:
        scenario = input(f"Scenario name (leave empty for scenario demo {scenario_default}): ")
        if scenario == '':
            scenario = scenario_default
        logger.info(f'{scenario}.yaml selected.')
        args.scenario_name = scenario

    act_wa = 'deactivated'
    act_rt = 'deactivated'
    if args.webdash:
        act_wa = 'activated'
    if args.real_time:
        act_rt = 'activated'

    logger.info(f"webdash dashboard {act_wa}. Real-Time simulation {act_rt}.")

    scenario = Scenario(filename=args.scenario_name, scenario_dir=args.scenario_dir)

    if scenario.data_collector_cfg:
        if args.webdash or 'ZMQ' in scenario.data_collector_cfg.keys():
            # Start webdash
            logger.info('WebDash starting..')
            from subprocess import Popen

            process = Popen(['python', 'webdash.py'])  # , stdout=PIPE)
            time.sleep(3)
            # flag = 0
            # while True:
            #     x = process.stdout.readline().strip().decode('utf-8')
            #     # if "Dash" in x:
            #     #     break
            #     logger.info(x)
            #     flag += 1
            #     if flag == 7:
            #         break
            logger.info('WebDash activated.')

    scenario.run()
