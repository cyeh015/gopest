import time
import json
import inspect

from mulgrids import *
from t2data import *
from t2listing import *

from gopest.common import Singleton
from gopest.common import TwoWayDict
from gopest.common import readList
from gopest.common import updateObj
from gopest.common import merge_dols
from gopest import obs_def

from gopest.utils.waiwera_listing import wlisting

OBS_USER_FUNC = dict(inspect.getmembers(obs_def,inspect.isfunction))
OBS_ALIAS = TwoWayDict(obs_def.shortNames)

class PestObsDataName(Singleton):
    """ remembers a list of observation data and observation data """
    def __init__(self):
        self.basenames = set([])
    def newName(self,basename):
        apnd = ' 01234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        i = 0
        newname = (basename + apnd[i]).strip()
        while newname in self.basenames:
            i += 1
            if i >= len(apnd):
                raise Exception('Unable to find unused obseration name for:' + basename)
                break
            newname = (basename + apnd[i]).strip()
        return newname
    def add(self,newname):
        self.basenames.add(newname)

class PestObservData(object):
    def __init__(self,OBSNME='',OBSVAL=0.0,WEIGHT=1.0,OBGNME=''):
        self.OBSNME=OBSNME
        self.OBSVAL=OBSVAL
        self.WEIGHT=WEIGHT
        self.OBGNME=OBGNME
    def __repr__(self):
        return  self.OBSNME +' '+ str(self.OBSVAL) +' '+ str(self.WEIGHT) +' '+ self.OBGNME

class UserEntryObserv(object):
    """
        user defined routines
    """
    def __init__(self,obsType,obsInfo,fieldDataFile,customFilter,
        offsetTime,obsDefault=PestObservData()):
        self.obsType = obsType # a string
        self.obsInfo = obsInfo # a list of anything
        self.fieldDataFile = fieldDataFile # a string
        self.customFilter = customFilter # an expression string
        self.offsetTime = offsetTime # a number to offset model time
        from copy import deepcopy
        self.obsDefault = deepcopy(obsDefault)

        self.all_obses = None
        self.all_pst_lines = None # should be a list of strings
        self.all_ins_lines = None # should be a list of strings
        self.all_obf_lines = None # should be a list of strings

        # this is expected to be directly written into self, by custom function
        self.batch_plot_entry = []
        self.coverage = {} # keyed by OBGNME, each group is a list of model blocks with data
    def __repr__(self):
        return '\n'.join([
            '','[Obs]',
            self.obsType,
            ';'.join([str(info) for info in self.obsInfo]),
            self.fieldDataFile,
            self.customFilter,
            str(self.obsDefault),
            ''])
    def makeObsDataInsLines(self,geo,dat):
        """ generate a tuple of two lists:
            - list of Pest * observation data """
        # maybe + ('%5s' % str(self.obsInfo[0])) with fill?
        if self.obsDefault.OBSNME == '':
            newBaseName = PestObsDataName().newName(OBS_ALIAS[self.obsType])
            PestObsDataName().add(newBaseName)
            # user def routines use this as basename
            self.obsDefault.OBSNME = newBaseName
        # use obsType if not specified by user
        if self.obsDefault.OBGNME == '':
            self.obsDefault.OBGNME = self.obsType

        ### this line does all the work
        self.all_obses = OBS_USER_FUNC[self.obsType+'_fielddata'](geo,dat,self)

        self.all_pst_lines = []
        self.all_ins_lines = []
        for obs in self.all_obses:
            self.all_ins_lines.append('l1 [%s]21:41' % obs.OBSNME)
            self.all_pst_lines.append(' %-20s %20.13e %12.5e %s' % (obs.OBSNME,
                obs.OBSVAL,obs.WEIGHT,obs.OBGNME))

    def makeObfLines(self,geo,dat,lst):
        """ generate a list of:
            - values for obf file that PEST requires """

        ### this line does all the work
        obfValues = OBS_USER_FUNC[self.obsType+'_modelresult'](geo,dat,lst,self)
        self.all_obf_lines = []
        for (v,obs) in zip(obfValues,self.all_obses):
            self.all_obf_lines.append('%-20s %20.13e' % (obs.OBSNME,v))

def readUserObservation(userListName):
    """ returns a list of UserEntryObserv from reading the file with name
        userObsListName """
    userEntries = []
    f = open(userListName,'r')
    entryName, entry = readList(f)
    f.close()
    # some defaults even if no sections exists:
    obsDefault = PestObservData()
    customFilter = 'True'
    offsetTime = 0.0
    for i,en in enumerate(entryName):
        if en == 'ObservationType':
            obsType = entry[i][0].strip()
            continue
        if en == 'DataFilter':
            if len(entry[i]) == 0:
                # reset
                customFilter = 'True'
            else:
                customFilter = entry[i][0]
        if en == 'DataTimeOffset':
            if len(entry[i]) == 0:
                # reset
                offsetTime = 0.0
            else:
                offsetTime = float(eval(entry[i][0]))
        if en == 'Defaults':
            obsDefault = updateObj(obsDefault,entry[i])
        # if en == 'Obs':
        #     if len(entry[i]) < 2: raise Exception
        #     if ',' in entry[i][0]:
        #         obsInfo = list(eval(entry[i][0]))
        #     else:
        #         obsInfo = [eval(entry[i][0])]
        #     for fieldDataFile in entry[i][1:]:
        #         userEntries.append(UserEntryObserv(obsType,obsInfo,
        #             fieldDataFile.strip(),customFilter,offsetTime,
        #             obsDefault))
        if en == 'Obs':
            if len(entry[i]) < 1:
                raise Exception("An empty [Obs] entry is found in goPESTobs.list")
            # pass the list of lines in, user functions to deal with them
            obsInfo = [s.rstrip('\n') for s in entry[i]]
            fieldDataFile = ''
            userEntries.append(UserEntryObserv(obsType,obsInfo,
                fieldDataFile.strip(),customFilter,offsetTime,
                obsDefault))
    return userEntries

def generate_obses_and_ins(fgeo, fdat, insToWrite, fobses, fplts='goPESTobs.json', fcovs='goPESTobs.coverage'):
    """ reads goPESTobs.list and generate observation data lines and instruction
    file for PEST """
    # reset unique obs name
    obs_def.obsBaseNameCount = {}
    geo = mulgrid(fgeo)
    if fdat.endswith('.json'):
        with open(fdat, 'r') as f:
            dat = json.load(f)
    else:
        dat = t2data(fdat)

    userEntries = readUserObservation('goPESTobs.list')
    pstLines, insLines, plots, coverage = [], [], [], {}
    for ue in userEntries:
        ue.makeObsDataInsLines(geo,dat)
        pstLines = pstLines + ue.all_pst_lines
        insLines = insLines + ue.all_ins_lines
        plots += ue.batch_plot_entry
        coverage = merge_dols(coverage, ue.coverage)

    f = open(insToWrite, 'w')
    f.write('pif #\n')
    for line in insLines:
        f.write(line+'\n')
    f.close()

    obs = open(fobses, 'w')
    for line in pstLines:
        obs.write(line + '\n')
    obs.close()

    plt = open(fplts, 'w')
    json.dump(plots, plt, indent=4, sort_keys=True)
    plt.close()

    cov = open(fcovs, 'w')
    json.dump(coverage, cov, indent=4, sort_keys=True)
    cov.close()

def read_from_real_model(fgeo, fdat, flst, fobf, waiwera=False):
    """ This reads TOUGH2's results and write in appropriate format into obf
    file for PEST """
    # reset unique obs name
    obs_def.obsBaseNameCount = {}
    geo = mulgrid(fgeo)
    if waiwera:
        with open(fdat, 'r') as f:
            dat = json.load(f)
        lst = wlisting(flst, geo, fjson=fdat)
    else:
        dat = t2data(fdat)
        if flst.lower().endswith('.h5'):
            lst = t2listingh5(flst)
        else:
            lst = t2listing(flst)

    userEntries = readUserObservation('goPESTobs.list')
    obfLines = []
    for ue in userEntries:
        ue.makeObsDataInsLines(geo,dat)
        ue.makeObfLines(geo,dat,lst)
        obfLines = obfLines + ue.all_obf_lines

    if flst.lower().endswith('.listing'):
        lst.close()

    f = open(fobf,'w')
    for line in obfLines:
        f.write(line+'\n')
    f.close()

def goPESTobs(argv=[]):
    START_TIME = time.time()

    userlistname = 'goPESTobs.list'

    if len(argv) not in [4,5]:
        print('to generate PEST .pst observation section and .ins: ')
        print('     gopest obs geo dat newPESTins')
        print('to read Tough2 results and write result file for PEST to read:')
        print('     gopest obs geo dat lst newPESTobf')

    if len(argv) == 4:
        fgeo = argv[1]
        fdat = argv[2]
        insToWrite = argv[3]

        fobses = 'pest_obs_data'
        fplts = 'goPESTobs.json'
        fcovs = 'goPESTobs.coverage'
        generate_obses_and_ins(fgeo, fdat, insToWrite,
                               fobses, fplts, fcovs)

    if len(argv) == 5:
        
        fgeo = argv[1]
        fdat = argv[2]
        flst = argv[3]
        obfToWrite = argv[4]

        geo = mulgrid(fgeo)
        if fdat.lower().endswith('.json'):
            with open(fdat, 'r') as f:
                dat = json.load(f)
        else:
            dat = t2data(fdat)
        
        if flst.lower().endswith('.listing'):
            lst = t2listing(flst)
        elif flst.lower().endswith('.h5'):
            if fdat.lower().endswith('.json'):
                lst = wlisting(flst, geo, fjson=fdat)
            else:
                lst = t2listingh5(flst)



        userEntries = readUserObservation(userlistname)
        obfLines = []
        for ue in userEntries:
            ue.makeObsDataInsLines(geo,dat)
            ue.makeObfLines(geo,dat,lst)
            obfLines = obfLines + ue.all_obf_lines


        f = open(obfToWrite,'w')
        for line in obfLines:
            f.write(line+'\n')
        f.close()
        
    # print('goPESTobs finished after', (time.time() - START_TIME), 'seconds')
        


