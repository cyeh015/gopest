# **goPEST**

goPEST is a set of utilities used to interface PEST with Waiwera and (AU)TOUGH2 simulators.


## Install

The easiest way to install goPEST is:

```python -m pip install gopest```


## Input files

User needs to prepare a few files for goPEST to work:

- `goPESTconfig.toml`, this file contains all settings/configurations related to the running of goPEST.  It is written in TOML file format.  The file should be placed in the project folder, where user runs gopest commands from.  It is possible to let goPEST generate one with default values.  The file tries to be self-explanatory with comments.

- `goPESTpar.list` is where user specifies model parameters for PEST

- `goPESTobs.list` is where user specifies model observations for PEST

- `goPESTuser.py` is optional if user wish do perform customised setups when the simulation transit from one stage to the next stage in sequence of simulator runs (eg. usually `ns` and `pr` normally natural state then followed by production history).

## Basic usage

The main CLI script `gopest` is to be followed by COMMAND and associated arguments:

```gopest COMMAND [ARGUMENTS]```

To get a list of supported COMMANDs, type `gopest help`.

The first step is to initialise the working directory:

```gopest init```

will setup the current folder.  If all goes well, user can simply run the command:

```gopest submit``` or
```gopest run``` 

to start the PEST run.  Command `submit` is for the NeSI cluster environment using SLURM.  Job(s) will be submitted to the cluster queue.  PEST master and agents will be launched automatically.  On a local machine where user has full access `gopest run` is used.

## How goPEST works

Several tasks were performed by the `init` command:

- copy user's model files into what goPEST uses internally, these are the `real_model_xxx.*` files, in the current folder, which is also the master folder where PEST is expected to work on.

- go through `goPESTpar.list`, extract and set up parameter data in the PEST control file (usually `case.pst`).  The corresponding `.tpl` files etc required by PEST will be set up.  Note the parameters used in the real model will be extracted and used as the initial parameters in the PEST.

- go through `goPESTobs.list`, and set up observation data in the PEST control file.  Corresponding PEST instruction file `.ins` will also be set up automatically.

## Development notes

- install an editable version of goPEST:

```python -m pip install -e /path/to/repo/root```

- run tests at the root of the repo:

```python -m pytest```

- generalised model sequence runner? now loads user goPESTuser.py, but internal needs to generalise to have more than two run sequence

- in run_ns_pr, code shouldn't worry about nesi/cluster related things, maybe
  not running local vs nesi either

- remove obsreref rekated things, use pest_hp now

- I have checked a few PEST related Python libraries.  I am looking for something small and pure for basic editing of PEST control file.  But these are too big for my liking.  I should reconsider about using them.
