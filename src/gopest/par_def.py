"""Definition file for parameter data types"""
#
# each function must accept three params: name,dat,val
#     names: t2data object names, eg. block, gener etc, must be a list
#     dat: your normal t2data object from PyTOUGH
#     val: a number that is going to be assigned, when not exist value
#          from dat will be returned, the first in the name list is used
#
# use existing entries as example to write new ones
# your new function name can then be used as 'param_type'
#
# the shortNames needs to be filled in, the right hand side
# string must be EXACTLY 3 characters wide, and NO SPACE
# these short names will be used as part of names in * parameter data
#

# TODO: consider using munch to allow access dictionary with object-oriented
# style? see:
# https://github.com/Infinidat/munch
# https://stackoverflow.com/questions/1305532/how-to-convert-a-nested-python-dict-to-object

import re

from gopest.common import getFromDict, setInDict

class ParDef(object):
    """ Base class for parameter, used to access model input parameters """
    def __init__(self, simulator):
        super(ParDef, self).__init__()
        if simulator not in ['aut2', 'waiwera']:
            raise Exception("simulator '%s' not supported." % simulator)
        self.simulator = simulator

    def get(self, dat, name):
        _get = getattr(self, 'get_' + self.simulator)
        return _get(dat, name)
    def get_aut2(self, dat, name):
        raise NotImplementedError(self.__class__.__name__)
    def get_waiwera(self, dat, name):
        raise NotImplementedError(self.__class__.__name__)

    def set(self, dat, name, value):
        _set = getattr(self, 'set_' + self.simulator)
        return _set(dat, name, value)
    def set_aut2(self, dat, name, value):
        raise NotImplementedError(self.__class__.__name__)
    def set_waiwera(self, dat, name, value):
        raise NotImplementedError(self.__class__.__name__)

    def find_names(self, dat, pattern):
        _find_names = getattr(self, 'find_names_' + self.simulator)
        return _find_names(dat, pattern)
    def find_names_aut2(self, dat, pattern):
        raise NotImplementedError(self.__class__.__name__)
    def find_names_waiwera(self, dat, pattern):
        raise NotImplementedError(self.__class__.__name__)

class permeability_1_byrock(ParDef):
    def get_aut2(self, dat, name):
        return dat.grid.rocktype[name].permeability[0]

    def set_aut2(self, dat, name, value):
        dat.grid.rocktype[name].permeability[0] = value

    def find_names_aut2(self, dat, pattern):
        pattern = re.compile(name)
        return [r.name for r in dat.grid.rocktypelist if pattern.match(r.name)]

    def get_waiwera(self, dat, name):
        for rock in dat['rock']['types']:
            if rock['name'] == name:
                return rock['permeability'][0]

    def set_waiwera(self, dat, name, value):
        for rock in dat['rock']['types']:
            if rock['name'] == name:
                rock['permeability'][0] = value

    def find_names_waiwera(self, dat, pattern):
        rex = re.compile(pattern)
        return [r['name'] for r in dat['rock']['types'] if rex.match(r['name'])]

class permeability_2_byrock(ParDef):
    def get_aut2(self, dat, name):
        return dat.grid.rocktype[name].permeability[1]

    def set_aut2(self, dat, name, value):
        dat.grid.rocktype[name].permeability[1] = value

    def find_names_aut2(self, dat, pattern):
        pattern = re.compile(name)
        return [r.name for r in dat.grid.rocktypelist if pattern.match(r.name)]

    def get_waiwera(self, dat, name):
        for rock in dat['rock']['types']:
            if rock['name'] == name:
                return rock['permeability'][1]

    def set_waiwera(self, dat, name, value):
        for rock in dat['rock']['types']:
            if rock['name'] == name:
                rock['permeability'][1] = value

    def find_names_waiwera(self, dat, pattern):
        rex = re.compile(pattern)
        return [r['name'] for r in dat['rock']['types'] if rex.match(r['name'])]

class permeability_3_byrock(ParDef):
    def get_aut2(self, dat, name):
        return dat.grid.rocktype[name].permeability[2]

    def set_aut2(self, dat, name, value):
        dat.grid.rocktype[name].permeability[2] = value

    def find_names_aut2(self, dat, pattern):
        pattern = re.compile(name)
        return [r.name for r in dat.grid.rocktypelist if pattern.match(r.name)]

    def get_waiwera(self, dat, name):
        for rock in dat['rock']['types']:
            if rock['name'] == name:
                return rock['permeability'][2]

    def set_waiwera(self, dat, name, value):
        for rock in dat['rock']['types']:
            if rock['name'] == name:
                rock['permeability'][2] = value

    def find_names_waiwera(self, dat, pattern):
        rex = re.compile(pattern)
        return [r['name'] for r in dat['rock']['types'] if rex.match(r['name'])]

class porosity_byrock(ParDef):
    def get_aut2(self, dat, name):
        return dat.grid.rocktype[name].porosity

    def set_aut2(self, dat, name, value):
        dat.grid.rocktype[name].porosity = value

    def find_names_aut2(self, dat, pattern):
        pattern = re.compile(name)
        return [r.name for r in dat.grid.rocktypelist if pattern.match(r.name)]

    def get_waiwera(self, dat, name):
        for rock in dat['rock']['types']:
            if rock['name'] == name:
                return rock['porosity']

    def set_waiwera(self, dat, name, value):
        for rock in dat['rock']['types']:
            if rock['name'] == name:
                rock['porosity'] = value

    def find_names_waiwera(self, dat, pattern):
        rex = re.compile(pattern)
        return [r['name'] for r in dat['rock']['types'] if rex.match(r['name'])]

class massgener_rate(ParDef):
    def get_aut2(self, dat, name):
        for g in dat.generatorlist:
            if g.name == name:
                return g.gx

    def set_aut2(self, dat, name, value):
        for g in dat.generatorlist:
            if g.name == name:
                g.gx = value
                return

    def find_names_aut2(self, dat, pattern):
        pattern = re.compile(name)
        return [g.name for g in dat.generatorlist if pattern.match(g.name)]

    def get_waiwera(self, dat, name):
        for source in dat['source']:
            if source['name'] == name:
                return source['rate']

    def set_waiwera(self, dat, name, value):
        for source in dat['source']:
            if source['name'] == name:
                source['rate'] = value

    def find_names_waiwera(self, dat, pattern):
        rex = re.compile(pattern)
        return [s['name'] for s in dat['source'] if rex.match(s['name'])]


class json_values(ParDef):
    def get_aut2(self, dat, name):
        """ expects name to be a tuple ([k1, k2, k3], last_key), where a list of
        keys k1,k2,k3 (can use either str or int) leading up to just before the
        last key.
        """
        cfg = getFromDict(dat.config, name[0])
        return cfg[name[1]]

    def set_aut2(self, dat, name, value):
        cfg = getFromDict(dat.config, name[0])
        cfg[name[1]] = value

    def find_names_aut2(self, dat, pattern):
        rex = re.compile(name)
        cfg = getFromDict(dat.config, name[0])
        return [(name[0], z) for z in cfg.keys() if rex.match(z)]


shortNames = {
'CJ' : 'json_values',
'HR' : 'heatgener_rate',
'SR' : 'massgener_rate',
'SE' : 'massgener_enth',
'IN' : 'infiltration',
'K1' : 'permeability_1',
'K2' : 'permeability_2',
'K3' : 'permeability_3',
'PO' : 'porosity',
'R1' : 'permeability_1_byrock',
'R2' : 'permeability_2_byrock',
'R3' : 'permeability_3_byrock',
'RA' : 'permeability_123_byrock',  #tgra963
'RS' : 'permeability_12_byrock',   #tgra963
'RP' : 'porosity_byrock',
'RE' : 'upflow_rech'
}


def upflow_rech(names, dat, val=None):
    if val is None:
        return dat.config['RechCoefficients'][names[0]]
    else:
        dat.config['RechCoefficients'][names[0]] = val

def heatgener_rate(names,dat,val=None):
    if val is None:
        for g in dat.generatorlist:
            if g.name in names:
                return g.gx
    else:
        for g in dat.generatorlist:
            if g.name in names:
                g.gx = val

def massgener_enth(names,dat,val=None):
    if val is None:
        for g in dat.generatorlist:
            if g.name in names:
                return g.ex
    else:
        for g in dat.generatorlist:
            if g.name in names:
                g.ex = val

def infiltration(names,dat,val=None):
    if val is None:
        return 999 # yet to be done
    else:
        # doesn't care names
        from make_rain import make_rain
        cfg_name = 'make_rain.cfg'
        cfg_name = os.getcwd() + os.path.sep + cfg_name
        cfg = config(cfg_name)
        [annualrain_const, annualrain_history,
            infiltration, raintemp, newwell_label, tim2sec, cols] = make_rain_proc_cfg(cfg)

        infiltration = val

        total_rain = make_rain(geo,dat,annualrain_const,infiltration,raintemp,newwell_label,
            60.0*60.0*24.0*365.25,cols)

def permeability_1(names,dat,val=None):
    if val is None:
        return dat.grid.block[names[0]].rocktype.permeability[0]
    else:
        from lib_rocktypes import update_rocktype_property_byblocks
        update_rocktype_property_byblocks('permeability[0]',names,dat,val)

def permeability_2(names,dat,val=None):
    if val is None:
        return dat.grid.block[names[0]].rocktype.permeability[1]
    else:
        from lib_rocktypes import update_rocktype_property_byblocks
        update_rocktype_property_byblocks('permeability[1]',names,dat,val)

def permeability_3(names,dat,val=None):
    if val is None:
        return dat.grid.block[names[0]].rocktype.permeability[2]
    else:
        from lib_rocktypes import update_rocktype_property_byblocks
        update_rocktype_property_byblocks('permeability[2]',names,dat,val)

def porosity(names,dat,val=None):
    if val is None:
        return dat.grid.block[names[0]].rocktype.porosity
    else:
        from lib_rocktypes import update_rocktype_property_byblocks
        update_rocktype_property_byblocks('porosity',names,dat,val)

def permeability_123_byrock(names,dat,val=None):
    if val is None:
        return dat.grid.rocktype[names[0]].permeability[0]
    else:
        dat.grid.rocktype[names[0]].permeability[0] = val
        dat.grid.rocktype[names[0]].permeability[1] = val
        dat.grid.rocktype[names[0]].permeability[2] = val

def permeability_12_byrock(names,dat,val=None):
    if val is None:
        return dat.grid.rocktype[names[0]].permeability[0]
    else:
        dat.grid.rocktype[names[0]].permeability[0] = val
        dat.grid.rocktype[names[0]].permeability[1] = val

