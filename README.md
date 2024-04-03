# Co-simulation and Optimization for Energy Systems Integration (COESI)

<img src="https://github.com/energycenterlab/COESI/blob/main/src/resources/assets/COESI_logo.png" width="128"/>

## Platform Overview

COESI will consist of a tool-chain to perform simulation of dynamic systems of different urban energy scenarios and use cases.

In the current release, the co-simulation architecture exploits Mosaik as the co-simulation engine (COE), which exposes API to integrates different simulators of models.

A simulator consist in the application of the Mosaik API to the model itself in order to use it in the scenario developed into Mosaik. The scenario design process and the scenario building procedure are designed to be flexible and agnostic with respect to the COE. Moreover, in future realises, the scenario design and implementation will be based on a semantic ontology by standardizing the scenario configuration procedure and the models required to run. It also eliminates the need for manual model linkage configuration. Since two attributes with the same units do not always imply the same meaning, the module will implement semantic interoperability to ensure consistency of data coupling across data types (integer, float, boolean, enumeration), units and dimensionality (kilogram, Joule, Watt), value ranges (minimum or maximum values), and semantic meaning of the attributes to be coupled.

The simulators can be diverse, e.g. data visualization, physical models, Multi-Agent System models, control models etc. Two simulators were developed to use FMU through the python libraries pyFMI and FMPy. Some of the already developed simulators were used adn adapted for our platform.

## Getting Started

### How to install

clone the repository COESI
Install python 3.8+ (64 bit)

visualstudio install builtools for FMI capabilities.

Install miniconda as package manager.

Go to the main directory of COESI and create the environmet:

    conda env create --file environment.yml

### How to use it
From command line, activate the environment:

    conda activate coesi

Go to coesi directory of the project. To run a simulation of the scenario demo, execute the following command:

    python coesi.py

if you want to choose the scenario and/or activate the web dashboard, run the following command:

    python coesi.py -s <scenario_name.yaml> -w <bool>

where <scenario_name.yaml> is the namefile of the scenario located in the scenarios directory. For <bool>, set 1/0 if you want to activate/deactivate the web dashboard

## Citing COESI
If you used COESI, please consider adding citations to the following papers about COESI:

    @article{schiera2021distributed,
      author={Schiera, Daniele Salvatore and Barbierato, Luca and Lanzini, Andrea and Borchiellini, Romano and Pons, Enrico and Bompard, Ettore and Patti, Edoardo and Macii, Enrico and Bottaccioli, Lorenzo},
      journal={IEEE Transactions on Industry Applications},
      title={A Distributed Multimodel Platform to Cosimulate Multienergy Systems in Smart Buildings},
      year={2021},
      volume={57},
      number={5},
      pages={4428-4440},
      keywords={Buildings;Load modeling;Analytical models;Tools;Resistance heating;Usability;Solid modeling;Building energy system (BES);cosimulation;cyber-physical multienergy system;distributed computing;electrical energy storage;functional mock-up interface (FMI);heat pump;Mosaik;photovoltaics (PV);system simulation},
      doi={10.1109/TIA.2021.3094497}}
