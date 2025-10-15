# mu2e-trig-config

This package is a part of the Mu2e TDAQ Suite

## Common DAQ Repositories

* [artdaq-core-mu2e](https://mu2e.github.io/daq-operations/doxygen/artdaq-core-mu2e): _artdaq_ Fragment data formats
* [mu2e-pcie-utils](https://mu2e.github.io/daq-operations/doxygen/mu2e-pcie-utils): PCIe Device Driver and interface library
* [artdaq-mu2e](https://mu2e.github.io/daq-operations/doxygen/artdaq-mu2e): Core data acquisition code
* [otsdaq-mu2e](https://mu2e.github.io/daq-operations/doxygen/otsdaq-mu2e): Slow controls and Front-End Interface
* [otsdaq-mu2e-dqm](https://mu2e.github.io/daq-operations/doxygen/otsdaq-mu2e-dqm): DQM interface and tools
* [mu2e-trig-config](https://mu2e.github.io/daq-operations/doxygen/mu2e-trig-config): Trigger path FHiCL generation utilities

## Subsystem-Specific Repositories

* [otsdaq-mu2e-calorimeter](https://mu2e.github.io/daq-operations/doxygen/otsdaq-mu2e-calorimeter)
* [otsdaq-mu2e-crv](https://mu2e.github.io/daq-operations/doxygen/otsdaq-mu2e-crv)
* [otsdaq-mu2e-extmon](https://mu2e.github.io/daq-operations/doxygen/otsdaq-mu2e-extmon)
* [otsdaq-mu2e-stm](https://mu2e.github.io/daq-operations/doxygen/otsdaq-mu2e-stm)
* [otsdaq-mu2e-tracker](https://mu2e.github.io/daq-operations/doxygen/otsdaq-mu2e-tracker)
* [otsdaq-mu2e-trigger](https://mu2e.github.io/daq-operations/doxygen/otsdaq-mu2e-trigger)

# Additional Documentation (Package-Specific)

This package houses the configuration files used to run the art executables in the TDAQ system. The package also includes a python script used to generate the configuration files for the TDAQ art jobs starting from a single JSON file.

## core
The main area houses a series of files used to configure the Online reconstruction and the trigger sequences:
- `trigProducers.fcl`: module instances of the producer modules used in the Online reconstruction
- `trigSequences.fcl`: sequences used in the trigger paths and Online reconstruction
- `trigFilters.fcl`  : module instances of the filter modules used in the Online reconstruction
- `trigServices.fcl` : place holder for teh services used in the Online reco 
- `trigDigiInputEpilog.fcl`: used only for Offline tests where the inout data are in a Digi format (not Fragments)

## data
This directory contains the Menu configuration files that organize in a single JSON file the configuration of the several components needed to run the `art`-based steps of the TDAQ state machine: Online reconstruction, trigger selection, dataloggers, DQM

## python
This directory houses the following scripts:
- `generateMenuFromJSON.py`: it creates the set of `fcl` files necessary to configure using the `data/physMenu.json` as input:
    1. the trigger sequences that use the tracker+calorimeter data: `trigMenuPSConfig.fcl`, `trigMenu.fcl`
    2. the trigger sequences that use the CRV (+possibly the Trk+Cal) data: `aggMenuPSConfig.fcl`, `aggMenu.fcl`
    3. the datalogger: `trigLoggerConfig.fcl`, `trigLoggerMenu.fcl`
    4. the lumiLogger: `trigLumiLoggerConfig.fcl`, `trigLumiLoggerMenu.fcl`
 It is also possible to specify only a specific event-mode in the trigger menu by using the option `-evtMode`; the possible options are: `all`, `OnSpill` and `OffSpill`.
 It is also possible to process a customized trigger-menu json file by using the option `-mf`. 

An example of command line is the following: 
`python mu2e-trig-config/python/generateMenuFromJSON.py -mf mu2e-trig-config/data/physMenu.json -o gen -evtMode all`
