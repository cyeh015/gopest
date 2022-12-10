from t2data import *
from gopest.common import TwoWayDict
from gopest.common import Singleton

# implementation:
#   a user entry is something simple a user can undersand and easily enter
#   these are entered as groups, each with type and settings.  these are
#   turned into what PEST requires.
#

# i need a dictionary, leys of parameter data type (short), which maps to
# functions from the user defined functions that can modify t2data objects

class PestParamGroups(object):
    """ representation of entries in PEST * parameter groups """
    def __init__(self,name,INCTYP='relative',DERINC=0.01,DERINCLB=0.0,
        FORCEN='switch',DERINCMUL=2.0,DERMTHD='parabolic'):
        self.PARGPNME = name
        self.INCTYP = INCTYP
        self.DERINC=DERINC
        self.DERINCLB=DERINCLB
        self.FORCEN=FORCEN
        self.DERINCMUL=DERINCMUL
        self.DERMTHD=DERINCMUL

        self.defPARLBND = 0.0
        self.defPARUBND = 0.0

class PestParamData(object):
    """ this is equalivalent to each of * parameter data in PEST.  it is
    able to write entries for PEST control file (.pst), and PEST template
    file (.tpl).  It is also responsible of reading PEST generated 'model'
    file and make real changes into Tough2 input file """
    #? do I have too many tasks for this class?
    def __init__(self,name='',PARTRANS='none',PARCHGLIM='factor',PARVAL1=1.0,
        PARLBND=0.5,PARUBND=1.5,PARGP='grp',SCALE=1.0,OFFSET=0.0,DERCOM=1,
        TEMPLATEWIDTH=7):
        self.PARNME = name
        self.PARTRANS=PARTRANS
        self.PARCHGLIM=PARCHGLIM
        self.PARVAL1=PARVAL1
        self.PARLBND=PARLBND
        self.PARUBND=PARUBND
        self.PARGP=PARGP
        self.SCALE=SCALE
        self.OFFSET=OFFSET
        self.DERCOM=DERCOM

        # this is not part of PEST's design, used by goPEST to determine the
        # correct template field width, which is related to the precision of
        # TOUGH2 input.  It should be 7 for a standard TOUGH2 entry, with 2
        # less for starting- and ending-mark, and one less because PEST has
        # better ability to squeeze one extra precision than Python using the
        # same width.  If using .pdat, you should probably use 12 (15-3) to get
        # the precision effect.
        self.TEMPLATEWIDTH = TEMPLATEWIDTH

    def write(self, f=None):
        """ expects f to be a file object ready to write(), otherwise print to screen """
        line = ' '.join([str(a) for a in [
            self.PARNME,
            self.PARTRANS,
            self.PARCHGLIM,
            self.PARVAL1,
            self.PARLBND,
            self.PARUBND,
            self.PARGP,
            self.SCALE,
            self.OFFSET,
            self.DERCOM,
            ]])
        if f is None:
            print(line)
        else:
            f.write(line + '\n')


import inspect
from gopest import par_def
PARAM_GETSET = dict(inspect.getmembers(par_def,inspect.isfunction))
PARAM_TYPE = PARAM_GETSET.keys()
PARAM_ALIAS = TwoWayDict(par_def.shortNames)

class PestParamDataName(Singleton):
    """ remembers a list of parameter data and observation data """
    def __init__(self):
        self.names = set([])
    def newName(self,basename):
        apnd = ' 01234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        i = 0
        newname = (basename + apnd[i]).strip()
        while newname in self.names:
            i += 1
            if i >= len(apnd):
                raise Exception('Unable to find unused parameter name for:' + basename)
                break
            newname = (basename + apnd[i]).strip()
        return newname
    def add(self,newname):
        self.names.add(newname)

class UserEntryParam(object):
    """ understands user entry group and its setings, type.  and will be
    responsible of creating PestParamData objects, as each * parameter data
    in PEST """
    def _matchRocktypes(dat,name):
        import re
        pat = re.compile(name)
        return [r.name for r in dat.grid.rocktypelist if pat.match(r.name)]
    def _matchElements(dat,name):
        import re
        pat = re.compile(name)
        return [b.name for b in dat.grid.blocklist if pat.match(b.name)]
    def _matchGenerators(dat,name):
        import re
        pat = re.compile(name)
        return [g.name for g in dat.generatorlist if pat.match(g.name)]
    def _matchConfigRechCoeff(dat,name):
        import re
        pat = re.compile(name)
        return [z for z in dat.config['RechCoefficients'].keys() if pat.match(z)]
    def _matchConfig(dat, key_name):
        # expects key_name as a tuple (keys, name) where keys is a list of "keys",
        # which can be strings or even integer, so that dat.config[key1][key2]...
        # can access the desired config entry

        keys, name = key_name
        cfg = getFromDict(dat.config, keys)
        import re
        pat = re.compile(name)
        # print("******", [(keys, z) for z in cfg.keys() if pat.match(z)])
        return [(keys, z) for z in cfg.keys() if pat.match(z)]
    match = {
        'Rocktype':_matchRocktypes,
        'Element':_matchElements,
        'Generator':_matchGenerators,
        'Config':_matchConfig,
        'ConfigRechCoeff':_matchConfigRechCoeff,
        }
    ListType = ['ForEach','SingleValue','TiedValues']
    def __init__(self,paramListType,paramList,t2objListType,t2objList,t2objType,dat,defaults=None):
        # paramListType  'ForEach' or 'SingleValue' or 'TiedValues'
        # paramList      a list of 'permeability_1' or 'porosity' etc
        # t2objListType  'ForEach' or 'SingleValue' or 'TiedValues'
        # t2objList      a list of PyTOUGH objects names 'aaa15' or 'BA***' etc
        # t2objType      one of 'Rocktype', 'Element', or 'Generator'
        # defaults       dict of default PestParamData of each PARAM_TYPE
        if paramListType not in self.ListType: print(paramListType, ' is not in ', ListType)
        if t2objListType not in self.ListType: print(t2objListType, ' is not in ', ListType)
        for p in [p for p in paramList if p not in PARAM_TYPE]: print(p, ' is not valid')
        self.t2objList = t2objList
        self.t2objType = t2objType
        self.paramListType=paramListType
        self.paramList=paramList
        self.t2objListType=t2objListType
        from copy import deepcopy
        self.defaults=deepcopy(defaults)

        # generate these by calling makeParamDataNames, pest *parameter data entries
        self.paramData = None
        self.ties = None

    def makeParamData(self,dat,tpl):
        """ generate a list of paramData and write to PEST template file"""
        # ??? Maybe I should make it spit tpl file entries, instead of write directly into file?
        if (self.paramData is not None) and (self.ties is not None): return
        self.paramData = []
        self.ties = []

        matchedList = []
        for n in self.t2objList:
            matched_names = self.match[self.t2objType](dat,n)
            for m in matched_names:
                if m not in matchedList:
                    matchedList.append(m)

        # if both ForEach
        for t2o in matchedList:
            for pt in self.paramList:
                if (pt in self.defaults) and (len(self.defaults[pt].PARNME) == 2):
                    # if set properly already (len=2), use the specified value
                    if isinstance(t2o, tuple):
                        nname = PestParamDataName().newName(self.defaults[pt].PARNME + private_cleanup_name(t2o[-1][:5]))
                    else:
                        nname = PestParamDataName().newName(self.defaults[pt].PARNME + private_cleanup_name(t2o))
                else:
                    # use PARAM_ALIAS as name base if not set properly
                    if isinstance(t2o, tuple):
                        nname = PestParamDataName().newName(PARAM_ALIAS[pt] + private_cleanup_name(t2o[-1][:5]))
                    else:
                        nname = PestParamDataName().newName(PARAM_ALIAS[pt] + private_cleanup_name(t2o))
                PestParamDataName().add(nname)
                if self.defaults is not None:
                    if pt in self.defaults:
                        from copy import deepcopy
                        pd = deepcopy(self.defaults[pt])
                    else:
                        pd = PestParamData()
                else:
                    pd = PestParamData()
                pd.PARNME = nname
                pd.PARVAL1 = PARAM_GETSET[pt]([t2o],dat)
                self.paramData.append(pd)
                theline = "$%-" + str(pd.TEMPLATEWIDTH) + 's$, %-20s, "%s"\n'
                tpl.write(theline % (nname, ('"%s"' % pt), str([t2o])))

def readUserParameter(userListName, dat):
    """ returns a list of UserEntryParam from reading the file with name
        userListName """
    userEntries = []
    f = open(userListName,'rU')
    entryName, entry = readList(f)
    f.close()
    # some defaults even if no sections exists:
    parDefaults = {}
    for i,en in enumerate(entryName):
        if en == 'Defaults':
            for line in entry[i]:
                if ':' in line:
                    ptype = [s.strip() for s in line.split(':')[0].split(',')]
                    for p in ptype:
                        if p not in parDefaults: parDefaults[p] = PestParamData()
                else:
                    for p in ptype:
                        updateObj(parDefaults[p],[line])
        if en == 'Param':
            if len(entry[i]) < 2: raise Exception
            tmp1, tmp2 = entry[i][0].split(':')
            paramListType = tmp1.strip()
            paramList = [s.strip() for s in tmp2.split(',')]
            tmp1, tmp2 = entry[i][1].split(':')
            t2objListType = tmp1.strip()
            t2objType = tmp2.strip()
            t2objList = []
            for line in entry[i][2:]:
                t2objList.append(eval(line))
            userEntries.append(UserEntryParam(paramListType,paramList,
                t2objListType,t2objList,t2objType,dat,parDefaults))
    return userEntries

def load_model_config(dat):
    """ Return config dict loaded from .json file with same model base name.
    """
    from os.path import splitext, basename, isfile
    import json
    jname = splitext(dat.filename)[0] + '.json'
    # print("*****", jname)
    if isfile(jname):
        with open(jname, 'rU') as jf:
            return json.load(jf)
    else:
        return {}

def save_model_config(dat, config):
    """ Saves config (dict) object into .json using same basename as t2data.
    """
    from os.path import splitext, basename
    import json
    jname = splitext(dat.filename)[0] + '.json'
    with open(jname, 'w') as jf:
        json.dump(config, jf, indent=4)

def generate_params_and_tpl(origInput, tplToWrite, par_data):
    """ this reads goPESTpar.list and generate appropriate template file and
    writes * parameter data lines into a file """
    dat = t2data(origInput)
    dat.config = load_model_config(dat)

    uentry = readUserParameter('goPESTpar.list', dat)

    parf = open(par_data, 'w')
    tpl = open(tplToWrite, 'w')
    tpl.write('ptf $\n')
    for up in uentry:
        up.makeParamData(dat,tpl)
        for pp in up.paramData:
            pp.write(parf)
    tpl.close()
    parf.close()

def generate_real_model(origInput, pestModel, realInput):
    """ this reads PEST generated model file and create the real TOUGH2 model
    """
    dat = t2data(origInput)
    dat.config = load_model_config(dat)
    pmodel = open(pestModel,'r')
    for line in pmodel.readlines():
        vals = eval(line.strip())
        pestValue, paramType, names = vals[0], vals[1], eval(vals[2])
        PARAM_GETSET[paramType](names,dat,pestValue)

    dat.write(realInput, extra_precision=True, echo_extra_precision=True)
    save_model_config(dat, dat.config)

def goPESTpar():
    #from config import *
    import os

    #cfg_name = os.path.split(__file__)[-1].split('.')[0] + '.cfg'
    #cfg = config().read_from_file(cfg_name)
    userlistname = os.path.split(__file__)[-1].split('.')[0] + '.list'



    import sys
    if len(sys.argv) not in [3,4]:
        print('to generate PEST .pst sections and .tpl (for once): ')
        print('     goPESTpar.py origINPUT newPESTtpl')
        print('to read PEST generated model file and create real INPUT for Tough2 (for each PEST forward run):')
        print('     goPESTpar.py origINPUT pestINPUT realINPUT')

    if len(sys.argv) == 3:
        origInput = sys.argv[1]
        tplToWrite = sys.argv[2]

        dat = t2data(origInput)
        dat.config = load_model_config(dat)

        uentry = readUserParameter(userlistname, dat)

        tpl = open(tplToWrite,'w')
        tpl.write('ptf $\n')
        for up in uentry:
            up.makeParamData(dat,tpl)
            for pp in up.paramData:
                pp.write()
        tpl.close()

    if len(sys.argv) == 4:
        origInput = sys.argv[1]
        pestModel = sys.argv[2]
        realInput = sys.argv[3]
        generate_real_model(origInput, pestModel, realInput)

