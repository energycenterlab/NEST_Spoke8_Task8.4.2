import os
import sys
from pathlib import Path
import yaml

pathroot = os.path.abspath(os.path.dirname(__file__))

PROJECT_ROOT = str(Path(__file__).resolve().parents[1]).replace('\\','/')
SCENARIO_ROOT = os.path.join(PROJECT_ROOT, 'scenarios').replace('\\','/')
COESI_ROOT = os.path.join(PROJECT_ROOT, 'src').replace('\\','/')
SIM_ROOT = os.path.join(COESI_ROOT, 'sims_api').replace('\\','/')
MODELS_ROOT = os.path.join(PROJECT_ROOT, 'models').replace('\\','/')
OUTPUTS_ROOT = os.path.join(PROJECT_ROOT, 'outputs').replace('\\','/')
RESOURCE_ROOT = os.path.join(COESI_ROOT, 'resources').replace('\\','/')
TEMP_ROOT = os.path.join(RESOURCE_ROOT, 'temp').replace('\\','/')

sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(1, COESI_ROOT)
sys.path.insert(2, SIM_ROOT)
sys.path.insert(3, MODELS_ROOT)

Path(TEMP_ROOT).mkdir(parents=True, exist_ok=True)

with open(os.path.join(SIM_ROOT,'mk_sims_api_config.yaml').replace('\\','/'), 'r') as stream:
    mk_sims_api_config = yaml.safe_load(stream)

