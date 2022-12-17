# **goPEST**

goPEST is a set of utilities used to interface PEST with Waiwera and (AU)TOUGH2 simulators.


## Install

The easiest way to install goPEST is:

```python -m pip install gopest```


## Basic usage

The main CLI script `gopest` is to be followed by COMMAND and associated arguments:

```gopest COMMAND [ARGUMENTS]```

To get a list of supported COMMANDs, type `gopest help`.


## TODO

- user run_ns_pr script? generalised model sequence runner?

- in run_ns_pr, code shouldn't worry about nesi/cluster related things, maybe
  not running local vs nesi either

- remove obsreref rekated things, use pest_hp now

