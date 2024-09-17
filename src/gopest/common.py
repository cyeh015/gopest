import os
import os.path
import string
import importlib.resources as resources
import shutil

# Access nested dictionary items via a list of keys
from functools import reduce  # forward compatibility for Python 3
import operator

import tomlkit


""" this allows gopest.common.config to be used directly, eg.
        from gopest.common import config as cfg
        print(cfg['pest']['executable'])
        print(cfg['simulator']['executable'])
"""
ftoml = 'goPESTconfig.toml'
try:
    with open(ftoml, 'r') as f:
        config = tomlkit.load(f)
except FileNotFoundError:
    print("Warning! Config file '%s' is not found in current (working) directory:" % ftoml)
    print("    %s" % os.getcwd())
    ans = input('Do you want goPEST to create a default file? (y/n) ')
    if 'y' in ans.lower():
        default_ftoml = resources.files('gopest.data') / ftoml
        with resources.as_file(default_ftoml) as f:
            shutil.copyfile(f, ftoml)
            print("Config file '%s' created, please review and re-run gopest." % ftoml)
            print("Existing...")
            exit(0)
    else:
        print("Error! A valid configuration file is required for goPEST to work.")
        print('Existing...')
        exit(1)

""" this allows gopest.common.runtime to be used directly, eg.
        from gopest.common import runtime
        print(runtime['filename']['fincon'])
        print(runtime['filename']['fdatns'])
"""
runtime = {}
def runtime_filenames(check=False):
    """ work out filenames for all internal model files """
    def getext(fn): return os.path.splitext(fn)[1].lower()
    all_geoms = ['g_real_model' + getext(f) for f in config['model']['original']['geometry-files']]
    input_typ = config['simulator']['input-type']
    output_typ = config['simulator']['output-type']
    sequence = config['model']['sequence']
    if input_typ == 'aut2':
        fsave = 'real_model_' + sequence[0] + '.save'
        fincon = 'real_model_' + 'incon' + '.incon'
        fdato = 'real_model_' + 'original' + '.dat'
        fdats = ['real_model_' + seq + '.dat' for seq in sequence]
        if output_typ == 'h5':
            flsts = ['real_model_' + seq + '.h5' for seq in sequence]
        else:
            flsts = ['real_model_' + seq + '.listing' for seq in sequence]
    elif input_typ == 'waiwera':
        fsave = 'real_model_' + sequence[0] + '.h5'
        fincon = 'real_model_' + 'incon' + '.h5'
        fdato = 'real_model_' + 'original' + '.json'
        fdats = ['real_model_' + seq + '.json' for seq in sequence]
        flsts = ['real_model_' + seq + '.h5' for seq in sequence]
    filenames = {
        # single string properties
        'geom': 'g_real_model.dat',
        'save': fsave,
        'incon': fincon,
        'dat_orig': fdato,
        # following peoperties are lists
        'all_geoms': all_geoms,
        'dat_seq': fdats,
        'lst_seq': flsts,
    }
    if check:
        for k,fnames in filenames.items():
            if not isinstance(fnames, list):
                fnames = [fnames]
            for fn in fnames:
                if not os.path.exists(fn):
                    raise Exception('Cannot find file %s in the working dir.' % fn)
    return filenames
runtime['filename'] = runtime_filenames()

########## utility classes and functions
class TwoWayDict(dict):
    def __init__(self,copyFrom=None):
        if copyFrom is not None:
            for k in copyFrom.keys():
                self[k] = copyFrom[k]
    def __len__(self):
        return dict.__len__(self) / 2
    def __setitem__(self, key, value):
        if key in self: raise Exception('TwoWayDict repeated key: %s' % str(key))
        dict.__setitem__(self, key, value)
        if value in self: raise Exception('TwoWayDict repeated key: %s' % str(value))
        dict.__setitem__(self, value, key)

class Singleton(object):
    __single = None # the one, true Singleton
    def __new__(classtype, *args, **kwargs):
        # Check to see if a __single exists already for this class
        # Compare class types instead of just looking for None so
        # that subclasses will create their own __single objects
        if classtype != type(classtype.__single):
            classtype.__single = object.__new__(classtype, *args, **kwargs)
        return classtype.__single

def readList(f):
    """ reads a file and returns a list of entries, an entry is a list strings
        all lines starts with '#' are ignored """
    entryName, entries = [], []
    for line in f.readlines():
        if len(line.strip()) == 0: continue  # empty lines
        if line.strip()[0] == '#': continue  # comment lines
        if line.strip()[0] == '[':           # [something] item opening
            tmp = line.strip()
            ikeyend=tmp.find(']')
            keyword=tmp[1:ikeyend]
            if keyword=='END': break         # [END] finishes all
            entryName.append(keyword)
            entries.append([])
            continue
        # all other non-empty lines parts of last entry (until [END])
        # error if some non-comment line apear above first keyword
        entries[-1].append(line)
    return (entryName, entries)

def updateDict(dic,lines):
    """ evaluate lines and update the content of the argument dictionary.  A KeyError
        exception is raised if the key from lines is not in dic.  Each line in lines
        is a simple string like 'key = val'. """
    keys,vals = [],[]
    for line in lines:
        if line.count('=') != 1: raise Exception
        k,v = line.split('=')
        if k.strip() not in dic:
            print(dic.keys())
            raise KeyError
        dic[k.strip()] = eval(v)
    return dic

def merge_dols(dol1, dol2):
    """ merging dicts of lists into a new dict of lists. """
    keys = set(dol1).union(dol2)
    no = []
    return dict((k, dol1.get(k, no) + dol2.get(k, no)) for k in keys)

def updateObj(obj,lines):
    """ evaluate lines and modify the members of the argument object, A KeyError
        exception is raised if the key from lines is not a member of the object.
        Each line in lines is a simple string like 'key = val'. """
    keys,vals = [],[]
    for line in lines:
        if line.count('=') != 1: raise Exception
        k,v = line.split('=')
        # if k.strip() not in obj.__dict__.keys():
        #     print(k, ' not supported, try: ', obj.__dict__.keys())
        #     raise KeyError
        setattr(obj,k.strip(),eval(v))
    return obj

def private_cleanup_name(s):
    """ cleans up string so no space, no funny symbols.  it will remove all
    punctuations chars apart from those specified in rep, which will be '_' """
    rep = ' .*'
    rmv = string.punctuation
    for c in rep: rmv = rmv.replace(c,'_')
    for c in rmv: s = s.replace(c,'')
    for c in rep: s = s.replace(c,'_')
    return s

def getFromDict(dataDict, mapList):
    return reduce(operator.getitem, mapList, dataDict)

def setInDict(dataDict, mapList, value):
    getFromDict(dataDict, mapList[:-1])[mapList[-1]] = value

