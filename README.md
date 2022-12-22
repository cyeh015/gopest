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


## Basic usage

The main CLI script `gopest` is to be followed by COMMAND and associated arguments:

```gopest COMMAND [ARGUMENTS]```

To get a list of supported COMMANDs, type `gopest help`.




## Development notes

- generalised model sequence runner? now loads user goPESTuser.py, but internal needs to generalise to have more than two run sequence

- in run_ns_pr, code shouldn't worry about nesi/cluster related things, maybe
  not running local vs nesi either

- remove obsreref rekated things, use pest_hp now

