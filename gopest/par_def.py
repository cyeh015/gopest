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

def json_values(key_name, dat, val=None):
    from goPESTcommon import getFromDict, setInDict
    keys, name = key_name[0]
    cfg = getFromDict(dat.config, keys)
    if val is None:
        return cfg[name]
    else:
        cfg[name] = val

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

def massgener_rate(names,dat,val=None):
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
def permeability_1_byrock(names,dat,val=None):
    if val is None:
        return dat.grid.rocktype[names[0]].permeability[0]
    else:
        dat.grid.rocktype[names[0]].permeability[0] = val
def permeability_2_byrock(names,dat,val=None):
    if val is None:
        return dat.grid.rocktype[names[0]].permeability[1]
    else:
        dat.grid.rocktype[names[0]].permeability[1] = val
def permeability_3_byrock(names,dat,val=None):
    if val is None:
        return dat.grid.rocktype[names[0]].permeability[2]
    else:
        dat.grid.rocktype[names[0]].permeability[2] = val

def porosity_byrock(names,dat,val=None):
    if val is None:
        return dat.grid.rocktype[names[0]].porosity
    else:
        dat.grid.rocktype[names[0]].porosity = val


