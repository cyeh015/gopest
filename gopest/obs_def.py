"""Definition file for observation data types"""

# each obsType should have TWO routines defined: _fielddata and _modelresult apended
# _fielddata(geo,dat,userEntry,obsDefault)
# _modelresult(geo,dat,lst,userEntry,obsDefault)

# userEntry is where input file (a list of observation specificaitions)
# each has obsType,obsInfo,fieldDataFile,customFilter,obsDefault
#
# obsInfo and fieldDataFile unique for each obs entry
# customFilter and obsDefault can be set or defaulted, mostly passed down
#     between onb entries unless modified.
#
# obsInfo is a list of items, specified as first line of each obs entry
#     it can be anything, eg. [string of name, number of time]
# fieldDataFile is a single string of ilename that the fielddata obs will be read from
#
# customFilter is a string that can be evaluated by the code to eg. limit range of
#     data etc
# obsDefault is an PestObservData object, the .OBSNME is the basename that should be
#     used for all created obs, other properties used as default.
#
# Each Observation is specified like this:
# [Obs]
# 1, 2, 3, 4, 5
# a_file_name.dat
#
# [Obs]
# 'abc'
# a_file_name.dat
# another_file.dat
#
# the first line (obsInfo) is always parsed by python, either as a list or a single value (of any type)
# the second and following line (fieldDataFile) are processed one by one, and will create different user entries.



# AY, May 2015
#
# I have done something major to allow the more flexible ways of specifying each observation.

from gopest.common import config as cfg

if 'waiwera' in cfg['simulator']['executable']:
    sim = 'waiwera'
else:
    sim = 'aut2'
FIELD = {
    'aut2': {
        'temp': 'Temperatu',
        'pres': 'Pressure',
        'pco2': 'CO2 partial pres',
        'rate': 'Generation rate',
        'enth': 'Enthalpy',
    },
    'waiwera':  {
        'temp': 'fluid_temperature',
        'pres': 'fluid_pressure',
        'pco2': 'fluid_CO2_partial_pressure',
        'rate': 'source_rate',
        'enth': 'source_enthalpy',
    },
}[sim]


PLOT_RAW_FIELD_DATA = True

shortNames = {
'Ex' : 'external',     # get obs value(s) from external source, thru json file
'En' : 'enthalpy',
'Ej' : 'enthalpy_json',
'Eb' : 'boiling',
'Bj' : 'boiling_json',
'Pr' : 'pressure',
'Pw' : 'pressure_by_well',
'Pb' : 'pressure_block_average',
'Pj' : 'pressure_block_average_json',
'Tw' : 'temperature',
'Th' : 'temperature_thickness',
'Tj' : 'temperature_thickness_json',
'Ti' : 'temp_interp_thickness_json',
'Tb' : 'blocktemperature',
'Hf' : 'heatflow',
'Hm' : 'heatflowminimum',
'Uf' : 'totalupflow',
'Ht' : 'totalheat',
'Se' : 'target_time',
}

# this for unique obs name
obsBaseNameCount = {}

def unique_obs_name(type_name, base):
    """ Form a unique observation name.  It will usually endup like
    XX_YYYYY_0012.  XX is shortNames[type_name], YYYYY is based on base and
    trimmed to 5 chars long.

    PEST max length of obs name is 20 chars.  If type_name is not one of the
    keys in shorNames, it will be used directly after trim to length of two.
    TODO: it's a bit ugly here, work on it!
    """
    base1 = type_name
    for s,t in shortNames.items():
        if t == type_name:
            base1 = s
    if base1 == type_name:
        base1 = type_name[:2]

    from gopest.common import private_cleanup_name
    base2 = private_cleanup_name(base)[:5]

    baseName = base1 +'_'+ base2
    if baseName not in obsBaseNameCount:
        obsBaseNameCount[baseName] = 0
    obsBaseNameCount[baseName] += 1
    if obsBaseNameCount[baseName] > 9999:
        raise Exception("Time to improve unique_obs_name()!")
    return baseName +'_'+ ('%04d' % obsBaseNameCount[baseName])

def _matchInputGeners(dat, reg_exp_list, gener_types):
    """ return a list of (name matched) actual generators (objects)

    Matches is done using a list of re objects (reg_exp_list).  And the gener
    must have type in the specified tpye list.  Fixed/unfixed names will be
    dealt with properly.
    """
    gs = []
    from mulgrids import unfix_blockname
    for g in dat.generatorlist:
        for r in reg_exp_list:
            if r.match(g.name) or r.match(unfix_blockname(g.name)):
                if g.type in gener_types:
                    gs.append(g)
                # already know this GENER is included, check next gener
    return gs

def external_fielddata(geo, dat, userEntry):
    """ This observation type is designed for observation value(s) that is not
    extractable from the .listing file that goPESTobs reads.  Hence user is
    responsible for getting the values externally, and then stores it in a json
    file for goPESTobs to read back in.

    [Obs]
    filename.json  # first line of entry is the json file storing the value(s)
    'data_key'     # the key name used to acces the json file
    140.0          # obs value (a single float?)

    [Obs]
    abc.json       # first line of entry is the json file storing the value(s)
    'data_name'    # the key name used to acces the json file
    5.0            # a list of values, len() must match from json
    7.0
    9.0

    [Obs]
    abc.json       # first line of entry is the json file storing the value(s)
    'data_name'    # the key name used to acces the json file
    1., 5.         # lines of tuple of two values
    2., 7.
    3., 9.
    # data from json file will be interp() to match these

    The motivation for this is the predictive run for Bacman case.  Where
    results from a second .listing file is required.  Instead of making
    goPESTobs reads multiple listing file, I decided to make it an external
    extraction.  Usually this kind of obs needs very specialised calculation and
    may not be all that re-usable.

    WIP, the need for reading multiple listing files is still needed, as
    projects like Lihir needs a whole series of runs, and all results from all
    runs may be important.  I will do this when I am doing big surgery in goPEST
    code next time.  Further investigation for best design is required.
    """
    import numpy as np
    from copy import deepcopy

    obsInfo = userEntry.obsInfo
    customFilter = userEntry.customFilter
    obsDefault = userEntry.obsDefault
    key = eval(obsInfo[1])        # usually use string as data key

    obses = []
    if len(obsInfo) == 3:
        expected = eval(obsInfo[2])
        if not isinstance(expected, float) and isinstance(expected, int):
            raise Exception
        ### single values
        expected = float(expected)
        obs = deepcopy(obsDefault)
        obs.OBSNME = unique_obs_name(obs.OBSNME, key)
        obs.OBSVAL = float(expected)
        obses.append(obs)
    elif len(obsInfo) > 3:
        expected = [eval(line) for line in obsInfo[2:]]
        if isinstance(expected[0], tuple):
            # list of tuples
            for x,y in expected:
                obs = deepcopy(obsDefault)
                obs.OBSNME = unique_obs_name(obs.OBSNME, key)
                obs.OBSVAL = y
                obses.append(obs)
        elif isinstance(expected[0], float) or isinstance(expected[0], int):
            # list of values
            for y in expected:
                obs = deepcopy(obsDefault)
                obs.OBSNME = unique_obs_name(obs.OBSNME, key)
                obs.OBSVAL = y
                obses.append(obs)
        else:
            raise Exception
    return obses

def external_modelresult(geo, dat, lst, userEntry):
    import numpy as np
    import json
    obsInfo = userEntry.obsInfo
    customFilter = userEntry.customFilter
    obsDefault = userEntry.obsDefault

    with open(obsInfo[0], 'r') as f:
        data = json.load(f)
    key = eval(obsInfo[1])        # usually use string as data key

    values = []
    if len(obsInfo) == 3:
        ### single values
        if not isinstance(data[key], float) and not isinstance(data[key], int):
            raise Exception
        values.append(float(data[key]))
    elif len(obsInfo) > 3:
        expected = [eval(line) for line in obsInfo[2:]]
        if isinstance(expected[0], tuple):
            ### x-y values
            if len(data[key][0]) != len(data[key][1]):
                msg = '%s [%s] does not not have matching xs,ys: ' % (obsInfo[0], key)
                msg += '%i != %i' % (len(data[key][0]), len(data[key][1]))
                raise Exception(msg)
            exs = [float(e[0]) for e in expected]
            vs = np.interp(exs, data[key][0], data[key][1])
            values += list(vs)
        elif isinstance(expected[0], float) or isinstance(expected[0], int):
            ### list of values
            if not isinstance(data[key], list) or len(data[key]) != len(expected):
                msg = '%s [%s] does not match dimension of expected: ' % (obsInfo[0], key)
                msg += str(expected)
                raise Exception(msg)
            values += [float(x) for x in data[key]]
        else:
            raise Exception
    return values

def target_time_fielddata(geo, dat, userEntry):
    obsInfo = userEntry.obsInfo
    customFilter = userEntry.customFilter
    obsDefault = userEntry.obsDefault

    expected_value = float(eval(obsInfo[0]))

    obses = []
    from copy import deepcopy
    obs = deepcopy(obsDefault)
    obs.OBSNME = unique_obs_name(obs.OBSNME, 'Se')
    obs.OBSVAL = float(expected_value)
    obses.append(obs)
    return obses

def target_time_modelresult(geo, dat, lst, userEntry):
    return [lst.fulltimes[-1]]

def totalheat_fielddata(geo,dat,userEntry):
    """ Extracting the total heat from specified GENERs (in dat/input file) as
    observation.

    [ObservationType]
    totalheat

    [Defaults]
    OBSNME = 'Heat'
    OBGNME = 'HtTotal'

    # !!! Note here uses all upper cases, don't touch other ObservationTypes
    [Obs]
    2000.00
    'abc99'
    'bbb99'
    'ccc99'

    # here it means an observation that adds up all heat in HEAT geners 'abc99',
    # 'bbb99', 'ccc99' (from data/input file) and the target of this sum is
    # 2000.0 J/s
    """
    obsInfo = userEntry.obsInfo
    customFilter = userEntry.customFilter
    obsDefault = userEntry.obsDefault

    expected_value = float(eval(obsInfo[0]))

    # check if entry matches anything
    import re
    res = [re.compile(eval(line)) for line in userEntry.obsInfo[1:]]
    gs = _matchInputGeners(dat, res, ['HEAT'])
    if len(gs) == 0:
        name = "'%s'" % ("','".join([r.pattern for r in res]))
        raise Exception("Specified gener names does not match any geners: %s" % name)

    if len(obsInfo) > 2:
        ap = '_'
    else:
        ap = ''

    obses = []
    from copy import deepcopy
    obs = deepcopy(obsDefault)
    obs.OBSNME = unique_obs_name(obs.OBSNME, eval(obsInfo[1]) + ap)
    obs.OBSVAL = float(expected_value)
    obses.append(obs)
    return obses

def totalheat_modelresult(geo,dat,lst,userEntry):
    #go through all mass geners and extract their rate, sum this and return the total value..
    import re
    res = [re.compile(eval(line)) for line in userEntry.obsInfo[1:]]
    gs = _matchInputGeners(dat, res, ['HEAT'])
    total = float(sum([g.gx for g in gs]))
    return [total]

def totalupflow_fielddata(geo,dat,userEntry):
    obsInfo = userEntry.obsInfo
    customFilter = userEntry.customFilter
    obsDefault = userEntry.obsDefault

    expected_value = float(eval(obsInfo[0]))

    if len(obsInfo) > 2:
        ap = '_'
    else:
        ap = ''

    obses = []
    from copy import deepcopy
    obs = deepcopy(obsDefault)
    obs.OBSNME = unique_obs_name(obs.OBSNME, eval(obsInfo[1]) + ap)
    obs.OBSVAL = float(expected_value)
    obses.append(obs)
    return obses

def totalupflow_modelresult(geo,dat,lst,userEntry):
    #go through all mass geners and extract their rate, sum this and return the total value..
    import re
    from mulgrids import unfix_blockname,fix_blockname
    res = []
    for line in userEntry.obsInfo[1:]:
        name = eval(line)
        res.append(re.compile(name))
    # these matchese should use the unfixed blockname rules
    total = 0.0
    for g in dat.generatorlist:
        for r in res:
            if r.match(g.name) or r.match(unfix_blockname(g.name)):
                if g.type in ('MASS','COM1'):
                    total += g.gx
                # already know this GENER is included, check next gener
                break
    return [total]


def heatflowminimum_fielddata(geo,dat,userEntry):
    expected_value = float(eval(userEntry.obsInfo[1]))
    customFilter = userEntry.customFilter
    obsDefault = userEntry.obsDefault
    zoneName = eval(userEntry.obsInfo[0])

    from gopest.common import private_cleanup_name
    baseName = obsDefault.OBSNME +'_'+ private_cleanup_name(zoneName)[:5]
    if baseName not in obsBaseNameCount:
        obsBaseNameCount[baseName] = 0
    obses = []
    obsBaseNameCount[baseName] += 1
    from copy import deepcopy
    obs = deepcopy(obsDefault)
    obs.OBSNME = baseName +'_'+ ('%04d' % obsBaseNameCount[baseName])
    obs.OBSVAL = expected_value
    obses.append(obs)
    return obses

def heatflowminimum_modelresult(geo,dat,lst,userEntry):
    expected_value = float(eval(userEntry.obsInfo[1]))
    customFilter = userEntry.customFilter
    obsDefault = userEntry.obsDefault
    zoneName = eval(userEntry.obsInfo[0])

    minimum = expected_value

    import config
    cfg = config.config('get_surface_heatflowminimum.cfg')

    from get_surface_heatflow import get_surface_heatflow_proc_cfg
    (geners,colsinzones,ListingTableNames,syear,coldenthalpy,
        show_fig,save_fig,outflow_only,calc_notinany
        ) = get_surface_heatflow_proc_cfg(cfg,geo,lst)

    if zoneName not in colsinzones: raise Exception("'%s' not in colsinzones" % zoneName + str(sorted(colsinzones.keys())))
    # so to skip other zones, still ineffecient, but that's it for now
    for z in colsinzones.keys():
        if z != zoneName: del colsinzones[z]

    from get_surface_heatflow import get_surface_heatflow
    (t_in_sec, zone_total, zone_area) = get_surface_heatflow(geo,lst,
        geners,colsinzones,ListingTableNames,syear,coldenthalpy,
        False,False,outflow_only,calc_notinany)

    # Only NS total heatflow (result index [-1]).  If model result is greater or
    # equal to the expected_value, than return expected_value, so it fits
    # perfectly as long as model result is > expected_value.
    if list(zone_total[zoneName])[-1] >= minimum:
        return [minimum]
    else:
        return [list(zone_total[zoneName])[-1]]



def heatflow_fielddata(geo,dat,userEntry):
    expected_value = float(eval(userEntry.obsInfo[1]))
    customFilter = userEntry.customFilter
    obsDefault = userEntry.obsDefault
    zoneName = eval(userEntry.obsInfo[0])

    from gopest.common import private_cleanup_name
    baseName = obsDefault.OBSNME +'_'+ private_cleanup_name(zoneName)[:5]
    if baseName not in obsBaseNameCount:
        obsBaseNameCount[baseName] = 0
    obses = []
    obsBaseNameCount[baseName] += 1
    from copy import deepcopy
    obs = deepcopy(obsDefault)
    obs.OBSNME = baseName +'_'+ ('%04d' % obsBaseNameCount[baseName])
    obs.OBSVAL = expected_value
    obses.append(obs)
    return obses

def heatflow_modelresult(geo,dat,lst,userEntry):
    expected_value = userEntry.obsInfo[1]
    customFilter = userEntry.customFilter
    obsDefault = userEntry.obsDefault
    zoneName = eval(userEntry.obsInfo[0])

    import config
    cfg = config.config('get_surface_heatflow.cfg')

    from get_surface_heatflow import get_surface_heatflow_proc_cfg
    (geners,colsinzones,ListingTableNames,syear,coldenthalpy,
        show_fig,save_fig,outflow_only,calc_notinany
        ) = get_surface_heatflow_proc_cfg(cfg,geo,lst)

    if zoneName not in colsinzones: raise Exception
    # so to skip other zones, still ineffecient, but that's it for now
    for z in colsinzones.keys():
        if z != zoneName: del colsinzones[z]

    from get_surface_heatflow import get_surface_heatflow
    (t_in_sec, zone_total, zone_area) = get_surface_heatflow(geo,lst,
        geners,colsinzones,ListingTableNames,syear,coldenthalpy,
        False,False,outflow_only,calc_notinany)

    # just get NS total heatflow for now
    return [list(zone_total[zoneName])[-1]]


def private_well_track_blocks(geo,wname):
    """ generate well track blocks if not already cached """
    if 'wellblocks' not in geo.__dict__:
        geo.wellblocks = {}
    if wname in geo.wellblocks:
        return geo.wellblocks[wname]
    else:
        # spped up, hopefully
        if 'qtree' not in geo.__dict__:
            geo.qtree = geo.column_quadtree()

        # work out all blocks
        w = geo.well[wname]
        blocks, blocks_cen = [], []
        for lc in [lay.centre for lay in geo.layerlist if w.bottom[2] <= lay.centre <= w.head[2]]:
            b = geo.block_name_containing_point(w.elevation_pos(lc),geo.qtree)
            if b is not None:
                blocks.append(b)
                blocks_cen.append(lc)

        # check if well head block is missed
        wh_col = geo.column_containing_point(w.head[:2],
            guess=geo.column[geo.column_name(blocks[0])],qtree=geo.qtree)
        for lay in geo.layerlist:
            if lay.bottom < wh_col.surface:
                wh_block_elev = (wh_col.surface + lay.bottom ) / 2.0
                wh_block = geo.block_name(lay.name,wh_col.name)
                break
        if wh_block not in blocks:
            blocks.insert(0, wh_block)
            blocks_cen.insert(0, wh_block_elev)
        geo.wellblocks[wname] = (blocks, blocks_cen)
        return geo.wellblocks[wname]

def _loadBlockTempFile(fname, customFilter):
    """ get all block names and temp out of field data file """
    from mulgrids import fix_blockname
    allblks, alltemp = [], []
    f = open(fname,'r')
    for line in f.readlines():
        if line.strip() == '': break
        block,temp = [eval(x) for x in line.split(',')[0:2]]
        if eval(customFilter):
            allblks.append(fix_blockname(block))
            alltemp.append(float(temp))
    f.close()
    return allblks, alltemp

def blocktemperature_fielddata(geo,dat,userEntry):
    """ a user field data file is a list of blocks with oberved temperature """
    fieldDataFile = userEntry.obsInfo[1]
    customFilter = userEntry.customFilter
    obsDefault = userEntry.obsDefault

    allblks, alltemp = _loadBlockTempFile(fieldDataFile, customFilter)

    from mulgrids import fix_blockname
    from copy import deepcopy
    obses = []
    for (b,t) in zip(allblks,alltemp):
        obs = deepcopy(obsDefault)
        obs.OBSNME = unique_obs_name(obsDefault.OBSNME, fix_blockname(b))
        obs.OBSVAL = t
        obses.append(obs)
    return obses

def blocktemperature_modelresult(geo,dat,lst,userEntry):
    """ a user field data file is a list of blocks with oberved temperature """
    fieldDataFile = userEntry.obsInfo[1]
    customFilter = userEntry.customFilter

    allblks, alltemp = _loadBlockTempFile(fieldDataFile, customFilter)

    vals = eval(userEntry.obsInfo[0])
    time = 0.0
    if isinstance(vals,tuple) and len(vals) == 2:
        time = float(vals[1])

    import numpy as np
    lst.index = np.abs(lst.fulltimes-time).argmin()

    field_name = [c for c in lst.element.column_name if c.startswith(FIELD['temp'])][0]

    return [lst.element[b][field_name] for b in allblks]

def temperature_fielddata(geo,dat,userEntry):
    # ugly, need re-writting and remove repeative actions
    fieldDataFile = userEntry.obsInfo[1]
    customFilter = userEntry.customFilter
    obsDefault = userEntry.obsDefault
    from mulgrids import fix_blockname
    vals = eval(userEntry.obsInfo[0])
    if isinstance(vals,str):
        # only wellname is specified
        wname = fix_blockname(vals)
    elif isinstance(vals,tuple):
        wname = fix_blockname(vals[0])

    # get temp vs elev from datafile first
    allelev, alltemp = [], []
    f = open(fieldDataFile,'r')
    for line in f.readlines():
        if line.strip() == '': break
        elev,temp = [float(x) for x in line.split()[0:2]]
        if eval(customFilter):
            allelev.append(elev)
            alltemp.append(temp)
    f.close()

    (bs, bs_c) = private_well_track_blocks(geo,wname)
    blocks, blocks_cen = [], []
    for (b,c) in zip(bs, bs_c):
        if allelev[-1] <= c <= allelev[0]:
            blocks.append(b)
            blocks_cen.append(c)

    # blocks and blocks_cen ready for use
    from numpy import interp
    blocks_temp = interp(blocks_cen,allelev[::-1],alltemp[::-1])

    from gopest.common import private_cleanup_name
    baseName = obsDefault.OBSNME +'_'+ private_cleanup_name(wname)[:5]
    if baseName not in obsBaseNameCount:
        obsBaseNameCount[baseName] = 0
    obses = []
    for (b,t) in zip(blocks,blocks_temp):
        obsBaseNameCount[baseName] += 1
        from copy import deepcopy
        obs = deepcopy(obsDefault)
        obs.OBSNME = baseName +'_'+ ('%04d' % obsBaseNameCount[baseName])
        obs.OBSVAL = t
        obses.append(obs)
    return obses

def temperature_modelresult(geo,dat,lst,userEntry):
    # ugly, need re-writting and remove repeative actions
    # maybe communication between pre- and post - process is still needed
    fieldDataFile = userEntry.obsInfo[1]
    customFilter = userEntry.customFilter
    obsDefault = userEntry.obsDefault
    from mulgrids import fix_blockname
    vals = eval(userEntry.obsInfo[0])
    time = 0.0
    if isinstance(vals,str):
        # only wellname is specified
        wname = fix_blockname(vals)
    elif isinstance(vals,tuple):
        wname = fix_blockname(vals[0])
        if len(vals) == 2:
            time = float(vals[1])

    # get temp vs elev from datafile first
    allelev, alltemp = [], []
    f = open(fieldDataFile,'r')
    for line in f.readlines():
        if line.strip() == '': break
        elev,temp = [float(x) for x in line.split()[0:2]]
        if eval(customFilter):
            allelev.append(elev)
            alltemp.append(temp)
    f.close()

    (bs, bs_c) = private_well_track_blocks(geo,wname)
    blocks = []
    for (b,c) in zip(bs, bs_c):
        if allelev[-1] <= c <= allelev[0]:
            blocks.append(b)

    import numpy as np
    lst.index = np.abs(lst.fulltimes-time).argmin()

    field_name = [c for c in lst.element.column_name if c.startswith(FIELD['temp'])][0]
    return [lst.element[b][field_name] for b in blocks]

def temperature_thickness_fielddata(geo,dat,userEntry):
    """ This is very simialr to the norml temperature obs type, only that the
    weight of each observation is assigned as the thickness of that layer.  The
    observation actually seen by PEST is saved as .obs files. """
    # ugly, need re-writting and remove repeative actions
    fieldDataFile = userEntry.obsInfo[1]
    customFilter = userEntry.customFilter
    obsDefault = userEntry.obsDefault
    from mulgrids import fix_blockname
    vals = eval(userEntry.obsInfo[0])
    if isinstance(vals,str):
        # only wellname is specified
        wname = fix_blockname(vals)
    elif isinstance(vals,tuple):
        wname = fix_blockname(vals[0])

    # get temp vs elev from datafile first
    allelev, alltemp = [], []
    f = open(fieldDataFile,'r')
    for line in f.readlines():
        if line.strip() == '': break
        elev,temp = [float(x) for x in line.split()[0:2]]
        if eval(customFilter):
            allelev.append(elev)
            alltemp.append(temp)
    f.close()

    (bs, bs_c) = private_well_track_blocks(geo,wname)
    blocks, blocks_cen, blocks_thickness = [], [], []
    for (b,c) in zip(bs, bs_c):
        if allelev[-1] <= c <= allelev[0]:
            blocks.append(b)
            blocks_cen.append(c)
            blocks_thickness.append(geo.layer[geo.layer_name(b)].thickness)

    # blocks and blocks_cen ready for use
    from numpy import interp
    blocks_temp = interp(blocks_cen,allelev[::-1],alltemp[::-1])

    fo = open(fieldDataFile+'.obs', 'w')
    for (z,t) in zip(blocks_cen,blocks_temp):
        fo.write('%.2f %.2f\n' % (z,t))
    fo.close()

    from gopest.common import private_cleanup_name
    baseName = obsDefault.OBSNME +'_'+ private_cleanup_name(wname)[:5]
    if baseName not in obsBaseNameCount:
        obsBaseNameCount[baseName] = 0
    obses = []


    if obsDefault.OBGNME not in userEntry.coverage:
        userEntry.coverage[obsDefault.OBGNME] = []
    for (b,t,h) in zip(blocks,blocks_temp, blocks_thickness):
        obsBaseNameCount[baseName] += 1
        from copy import deepcopy
        obs = deepcopy(obsDefault)
        obs.OBSNME = baseName +'_'+ ('%04d' % obsBaseNameCount[baseName])
        obs.OBSVAL = t
        obs.WEIGHT = h * obsDefault.WEIGHT
        userEntry.coverage[obsDefault.OBGNME].append(b)
        obses.append(obs)
    return obses

def temperature_thickness_modelresult(geo,dat,lst,userEntry):
    return temperature_modelresult(geo,dat,lst,userEntry)

def _well_interp_layers(wname, geo):
    """
    WARNING: this can be very problematic at the surface layers near wellhead.
    There would be cases where blocks involved is partial layer, then the
    interpolation would wrongly use layer centre as interpolation in 2D.
    """
    well = geo.well[wname]
    # cache qtree/kdtree for faster repeated searching
    if not hasattr(geo, 'kdtree'): geo.kdtree = geo.get_node_kdtree()
    if not hasattr(geo, 'qtree'): geo.qtree = geo.column_quadtree()

    interp_block_i, well_poses, elevs = [], [], []
    for lay in geo.layerlist[1:]:
        pos = well.elevation_pos(lay.centre, extend=False)
        if pos is None:
            # skip, well pos above or below well track
            continue

        nearest_node = geo.node_nearest_to(pos[:2], kdtree=geo.kdtree)
        well_col = geo.column_containing_point(pos[:2], qtree=geo.qtree)
        well_bname = geo.block_name_containing_point(pos, qtree=geo.qtree)

        if well_bname is None:
            # well block not in model, skip layer
            continue

        blocks_i = [] # block index for slicing listing table
        points = []
        for col in nearest_node.column | well_col.neighbour:
            bname = geo.block_name(lay.name, col.name)
            try:
                blocks_i.append(geo.block_name_index[bname])
            except KeyError:
                # incomplete layer, just use well block
                interp_block_i.append([geo.block_name_index[well_bname]])
                well_poses.append(pos)
                elevs.append(lay.centre)
                # next layer
                continue

        interp_block_i.append(blocks_i)
        well_poses.append(pos)
        elevs.append(lay.centre)
    return interp_block_i, well_poses, elevs

def _well_interp_temp(block_i_by_layer, well_poses, geo, lst):
    """ block_i_by_layer is a list of lists, each a group of block indices to
    interpolate temperature data.  well_poses is a list of pos, one for each
    layers same as block_i_by_layer.
    """
    import scipy.interpolate as interpolate
    # will cause error if no field name found
    for field in lst.element.column_name:
        if field.startswith('Temperatu'):
            field_name = field
            break
    temps = []
    for blocks_i, pos in zip(block_i_by_layer, well_poses):
        v = lst.element[field_name][blocks_i]
        cols = [geo.column_name(geo.block_name_list[bi]) for bi in blocks_i]
        points = [geo.column[c].centre for c in cols]
        if len(points) > 1:
            vi = interpolate.griddata(points, v, [pos[:2]], method='linear')
            temps.append(vi[0])
        else:
            temps.append(v[0])
    return temps


def temp_interp_thickness_json_fielddata(geo,dat,userEntry):
    jfilename = userEntry.obsInfo[0]
    customFilter = userEntry.customFilter
    offsetTime = userEntry.offsetTime
    obsDefault = userEntry.obsDefault
    tFactor = 365.25*24.*60.*60.

    import json
    # 1st line is json file name (of all wells)
    with open(jfilename, 'r') as f:
        t_bywell = json.load(f)

    obses = []

    for oline in userEntry.obsInfo[1:]:
        wname = eval(oline)
        if 'geo_well_name' in t_bywell[wname]:
            geo_wname = t_bywell[wname]['geo_well_name']
        else:
            geo_wname = wname
        time = t_bywell[wname]['time']
        allelev, alltemp = [], []
        for elev,temp in zip(t_bywell[wname]['elevations'],
                             t_bywell[wname]['temperatures']):
            if eval(customFilter):
                allelev.append(elev)
                alltemp.append(temp)

        # bis, wps, es = blk indices, well positions, elevations
        bis, wps, es = _well_interp_layers(geo_wname, geo)
        blocks, blocks_cen, blocks_thickness = [], [], []
        bis2, wps2, es2, bhs2 = [], [], [], []
        for bidx, wpos, elev in zip(bis, wps, es):
            if elev > allelev[0] or elev < allelev[-1]:
                # skip if out of field data range
                continue
            if eval(customFilter):
                bis2.append(bidx)
                wps2.append(wpos)
                es2.append(elev)
                # all same layer, just use first one
                lay = geo.layer_name(geo.block_name_list[bidx[0]])
                bhs2.append(geo.layer[lay].thickness)

        # blocks and blocks_cen ready for use
        from numpy import interp
        blocks_temp = interp(es2, allelev[::-1],alltemp[::-1])

        from gopest.common import private_cleanup_name
        baseName = obsDefault.OBSNME +'_'+ private_cleanup_name(geo_wname)[:5]
        if baseName not in obsBaseNameCount:
            obsBaseNameCount[baseName] = 0

        if obsDefault.OBGNME not in userEntry.coverage:
            userEntry.coverage[obsDefault.OBGNME] = []
            userEntry.coverage[obsDefault.OBGNME+'_interp_source'] = []



        for bidx,pos,t,h in zip(bis2, wps2, blocks_temp, bhs2):
            obsBaseNameCount[baseName] += 1
            from copy import deepcopy
            obs = deepcopy(obsDefault)
            obs.OBSNME = baseName +'_'+ ('%04d' % obsBaseNameCount[baseName])
            obs.OBSVAL = t
            obs.WEIGHT = h * obsDefault.WEIGHT
            # additional for model result extraction
            obs._bindx_ = bidx
            obs._wpos_ = pos
            obs._dtime_ = time * tFactor - offsetTime # data's time tag
            blks = [geo.block_name_list[i] for i in bidx]
            userEntry.coverage[obsDefault.OBGNME] = userEntry.coverage[obsDefault.OBGNME] + blks
            userEntry.coverage[obsDefault.OBGNME+'_interp_source'].append((
                obs.OBSNME, bidx))
            obses.append(obs)

        # generate batch plot entries
        plot = temperature_plot(
            geo_wname, time, list(es2), list(blocks_temp),
            baseName, ('Well %s at time %f' % (wname,time)) )
        if PLOT_RAW_FIELD_DATA:
            y, x = t_bywell[wname]['elevations'], t_bywell[wname]['temperatures']
            plot = plot_append_raw_data(plot, 'raw_'+wname, x, y, xunit="degC", yunit="meter")
        userEntry.batch_plot_entry.append(plot)

    return obses

def temp_interp_thickness_json_modelresult(geo,dat,lst,userEntry):
    import numpy as np
    import scipy.interpolate as interpolate
    # will cause error if no field name found
    for field in lst.element.column_name:
        if field.startswith(FIELD['temp']):
            field_name = field
            break
    print('+++ use field: %s' % field_name)

    obses = temp_interp_thickness_json_fielddata(geo, dat, userEntry)
    vals = []

    t_prev = obses[0]._dtime_
    lst.index = np.abs(lst.fulltimes-t_prev).argmin()
    for obs in obses:
        bis = obs._bindx_
        wps = obs._wpos_
        t = obs._dtime_

        # TODO, this is slow, can be much faster
        if t != t_prev:
            lst.index = np.abs(lst.fulltimes-t).argmin()
            t_prev = t

        v = lst.element[field_name][bis]
        cols = [geo.column_name(geo.block_name_list[bi]) for bi in bis]
        points = [geo.column[c].centre for c in cols]
        if len(points) > 1:
            vi = interpolate.griddata(points, v, [wps[:2]], method='linear')
            vals.append(vi[0])
        else:
            vals.append(v[0])
    return vals


def temperature_thickness_json_fielddata(geo,dat,userEntry):
    """ This is very simialr to the norml temperature obs type, only that the
    weight of each observation is assigned as the thickness of that layer.  The
    observation actually seen by PEST is saved as .obs files. """
    # ugly, need re-writting and remove repeative actions
    jfilename = userEntry.obsInfo[0]
    customFilter = userEntry.customFilter
    offsetTime = userEntry.offsetTime
    obsDefault = userEntry.obsDefault
    tFactor = 365.25*24.*60.*60.

    import json
    # 1st line is json file name (of all wells)
    with open(jfilename, 'r') as f:
        t_bywell = json.load(f)

    obses = []

    for oline in userEntry.obsInfo[1:]:
        wname = eval(oline)
        if 'geo_well_name' in t_bywell[wname]:
            geo_wname = t_bywell[wname]['geo_well_name']
        else:
            geo_wname = wname
        time = t_bywell[wname]['time']
        allelev, alltemp = [], []
        for elev,temp in zip(t_bywell[wname]['elevations'], t_bywell[wname]['temperatures']):
            if eval(customFilter):
                allelev.append(elev)
                alltemp.append(temp)

        if len(allelev) <= 1:
            print('temperature_thickness_json: User entry has no data, skipping: %s' % wname)
            continue

        (bs, bs_c) = private_well_track_blocks(geo,geo_wname)
        blocks, blocks_cen, blocks_thickness = [], [], []
        for (b,c) in zip(bs, bs_c):
            if allelev[-1] <= c <= allelev[0]:
                blocks.append(b)
                blocks_cen.append(c)
                blocks_thickness.append(geo.layer[geo.layer_name(b)].thickness)

        # blocks and blocks_cen ready for use
        from numpy import interp
        blocks_temp = interp(blocks_cen,allelev[::-1],alltemp[::-1])

        from gopest.common import private_cleanup_name
        baseName = obsDefault.OBSNME +'_'+ private_cleanup_name(geo_wname)[:5]
        if baseName not in obsBaseNameCount:
            obsBaseNameCount[baseName] = 0

        if obsDefault.OBGNME not in userEntry.coverage:
            userEntry.coverage[obsDefault.OBGNME] = []
        for (b,t,h) in zip(blocks,blocks_temp, blocks_thickness):
            obsBaseNameCount[baseName] += 1
            from copy import deepcopy
            obs = deepcopy(obsDefault)
            obs.OBSNME = baseName +'_'+ ('%04d' % obsBaseNameCount[baseName])
            obs.OBSVAL = t
            obs.WEIGHT = h * obsDefault.WEIGHT
            # additional for model result extraction
            obs._block_ = b
            obs._dtime_ = time * tFactor - offsetTime # data's time tag
            userEntry.coverage[obsDefault.OBGNME].append(b)
            obses.append(obs)

        # generate batch plot entries
        plot = temperature_plot(
            geo_wname, time, blocks_cen, list(blocks_temp),
            baseName, ('Well %s at time %f' % (wname,time)) )
        if PLOT_RAW_FIELD_DATA:
            y, x = t_bywell[wname]['elevations'], t_bywell[wname]['temperatures']
            plot = plot_append_raw_data(plot, 'raw_'+wname, x, y, xunit="degC", yunit="meter")
        userEntry.batch_plot_entry.append(plot)
        # generate batch plot entries
        # userEntry.batch_plot_entry.append(temperature_plot(
        #     wname, time, allelev, alltemp,
        #     baseName, ('Well %s at time %f' % (wname,time)) ))

    return obses

def temperature_thickness_json_modelresult(geo,dat,lst,userEntry):
    import numpy as np
    obses = temperature_thickness_json_fielddata(geo, dat, userEntry)
    vals = []
    t_prev = obses[0]._dtime_
    lst.index = np.abs(lst.fulltimes-t_prev).argmin()
    for obs in obses:
        b = obs._block_
        t = obs._dtime_

        # TODO, this is slow, can be much faster
        if t != t_prev:
            lst.index = np.abs(lst.fulltimes-t).argmin()
            t_prev = t

        vals.append(lst.element[b][FIELD['temp']])
    return vals

def temperature_plot(wname, time, elevs, temps, obsname, title):
    """ for (timgui) batch plotting """
    return {
        "series": [
            {
                "variable": FIELD["temp"],
                "well": wname,
                "timeunit": "year",
                "type": "DownholeWellSeries",
                "time": time
            },
            {
                "frozen_x": temps,
                "frozen_y": elevs,
                "xunit": "degC",
                "yunit": "meter",
                "name": obsname,
                "original_series": "",
                "type": "FrozenDataSeries"
            }
        ],
        "ylabel": "Elevation",
        "xlabel": "Temperature",
        "title": title
    }


def pressure_fielddata(geo,dat,userEntry):
    """ called by goPESTobs.py """
    entries = private_history_data(userEntry, 100000.0, 365.25*24.*60.*60.)
    obses, times = zip(*entries)
    return obses
def pressure_modelresult(geo,dat,lst,userEntry):
    from mulgrids import fix_blockname
    # name,timelist
    name = fix_blockname(eval(userEntry.obsInfo[0]))
    entries = private_history_data(userEntry, 100000.0, 365.25*24.*60.*60.)
    obses, timelist = zip(*entries)
    tbl = lst.history([('e',name,'Pressure')])
    if tbl is None:
        raise Exception("Observation (type pressure) '%s' does not match any block." % name)
    alltimes = tbl[0] # assuming all times are the same
    allpress = tbl[1]
    from numpy import interp
    return list(interp(timelist,alltimes,allpress))

def pressure_by_well_fielddata(geo,dat,userEntry):
    """ called by goPESTobs.py """
    entries = private_history_data(userEntry, 100000.0, 365.25*24.*60.*60.)
    if len(entries) == 0:
        raise Exception("User entry yields no observation: " + str(userEntry))
    obses, times = zip(*entries)
    return obses
def pressure_by_well_modelresult(geo,dat,lst,userEntry):
    """ expects a well name and elevation in first line, eg: 'WK  1', -100.0 """
    from mulgrids import fix_blockname
    # name,timelist
    # name = fix_blockname(eval(userEntry.obsInfo[0]))
    wname, elev = eval(userEntry.obsInfo[0])
    elev = float(elev)
    if wname not in geo.well:
        raise Exception("Obs type 'pressure_by_well' well %s does not exist in geometry file." % wname)
    pos = geo.well[wname].elevation_pos(elev, extend=True)
    # spped up, hopefully
    if 'qtree' not in geo.__dict__:
        geo.qtree = geo.column_quadtree()
    name = geo.block_name_containing_point(pos, geo.qtree)
    if name is None:
        raise Exception("Obs type 'pressure_by_well' well %s at %f is outside of the model." % (wname, elev))

    # print wname, elev, name
    entries = private_history_data(userEntry, 100000.0, 365.25*24.*60.*60.)
    obses, timelist = zip(*entries)
    tbl = lst.history([('e',name,'Pressure')])
    if tbl is None:
        raise Exception("Obs failed to extract Pressure for block %s." % name)
    alltimes = tbl[0] # assuming all times are the same
    allpress = tbl[1]
    from numpy import interp
    return list(interp(timelist,alltimes,allpress))

def target_times(desired_times, limit, data):
    """ work out target times (among desired_times) that has data within +-
    limit """
    def count_valid(time, limit, data):
        """ Assuming data is a list of tuple (t,y), count how many t is
        within the range of time +- limit. """
        i = 0
        for t,y in data:
            if (time-limit) <= t <= (time+limit):
                i += 1
        return i
    targets = []
    for time in desired_times:
        if count_valid(time, limit, data):
            targets.append(time)
    return targets

def calc_bz(geo, w, elev):
    pos = geo.well[w].elevation_pos(elev, extend=True)
    if 'qtree' not in geo.__dict__:
        geo.qtree = geo.column_quadtree()
    b = geo.block_name_containing_point(pos, geo.qtree)
    if b is None:
        raise Exception("well %s at %f is outside of the model." % (w, pcp))
    return b, geo.block_centre(geo.layer_name(b), geo.column_name(b))[2]

def pressure_plot(bname, dataname, ts, ps, title):
    """ for (timgui) batch plotting """
    return {
        "series": [
            {
                "type": "HistoryBlockSeries",
                "block": bname,
                "variable": FIELD["pres"]
            },
            {
                "type": "FrozenDataSeries",
                "name": dataname,
                "original_series": "",
                "frozen_x": [t for t in ts],
                "frozen_y": [p*1.0e5 for p in ps],
                "xunit": "t2year",
                "yunit": "pascal",
            }
        ],
        "ylabel": "Pressure",
        "xlabel": "Time",
        "title": title
    }

def plot_append_raw_data(plot, name, x, y, xunit="", yunit=""):
    plot["series"].append({
                              "type": "FrozenDataSeries",
                              "name": name,
                              "original_series": "",
                              "frozen_x": x,
                              "frozen_y": y,
                              "xunit": xunit,
                              "yunit": yunit,
                          })
    return plot

def pressure_block_average_fielddata(geo, dat, userEntry):
    customFilter = userEntry.customFilter
    offsetTime = userEntry.offsetTime
    obsDefault = userEntry.obsDefault
    vFactor, tFactor = 100000.0, 365.25*24.*60.*60.

    # check all required settings exists:
    must_have = ['_DESIRED_DATA_TIMES', '_INTERP_LIMIT', '_P_GRADIENT']
    if any([not hasattr(obsDefault,a) for a in must_have]):
        raise Exception('Obs type pressure_block_average must have these default settings: ' + ', '.join(must_have))

    p_byblock = {}

    for oline in userEntry.obsInfo:
        wname, elev, fwell = eval(oline)
        elev = float(elev)

        f = open(fwell,'r')
        times, vals = [], []
        for line in f.readlines():
            if line.strip() == '': break
            time,val = [float(x) for x in line.split()[0:2]]
            if eval(customFilter):
                times.append(time), vals.append(val)
        f.close()

        if len(times) == 0:
            f.close()
            raise Exception("Pressure file: %s yields no observation" % fwell)

        desired_times = obsDefault._DESIRED_DATA_TIMES
        interp_limit = obsDefault._INTERP_LIMIT
        p_gradient = obsDefault._P_GRADIENT

        # correct to block centre
        b, bz = calc_bz(geo, wname, elev)
        vals = [p - (bz-elev) * p_gradient for p in vals]

        # get times and vals for each line (well)
        final_times = [t for t in desired_times if times[0] <= t <= times[-1]]
        final_times = target_times(desired_times, interp_limit, zip(times,vals))
        if len(final_times) == 0:
            raise Exception("User entry yields no observation: " + oline)
        from numpy import interp
        final_vals = list(interp(final_times,times,vals))

        if b not in p_byblock:
            p_byblock[b] = []
        # each block have a list (ts, ps), one for each well in block
        p_byblock[b].append((final_times, final_vals, wname))

    # one series of obs for each block, averaging all these in the same block
    obses = []
    for b in sorted(p_byblock.keys()):
        # fo = open('p_byblock_%s.obs' % b.replace(' ','_'), 'w')
        bp_times = {}
        ws = []
        for dtimes, dvals, wname in p_byblock[b]:
            ws.append(wname)
            for ft,fv in zip(dtimes, dvals):
                if ft not in bp_times:
                    bp_times[ft] = []
                bp_times[ft].append(fv)

        avgt, avgp = [], []
        for t in sorted(bp_times.keys()):
            avgt.append(t)
            avgp.append(sum(bp_times[t]) / len(bp_times[t]))

        from gopest.common import private_cleanup_name
        from copy import deepcopy
        baseName = obsDefault.OBSNME +'_'+ private_cleanup_name(b)
        if baseName not in obsBaseNameCount:
            obsBaseNameCount[baseName] = 0
        for time, val in zip(avgt, avgp):
            obsBaseNameCount[baseName] += 1

            obs = deepcopy(obsDefault)
            obs.OBSNME = baseName +'_'+ ('%04d' % obsBaseNameCount[baseName])
            obs.OBSVAL = val * vFactor
            # additional for model result extraction
            obs._block_ = b
            obs._mtime_ = time * tFactor - offsetTime
            obses.append(obs)
            # output data file in original unit (instead of PEST/TOUGH2)
            # fo.write('%e %e\n' % (time, val))

        # generate batch plot entries
        userEntry.batch_plot_entry.append(pressure_plot(
            b, baseName, [t-offsetTime/(60.0*60.0*24.0*365.25) for t in avgt], avgp,
            b+': '+','.join(ws)))

        # fo.close()
    return obses

def pressure_block_average_modelresult(geo,dat,lst,userEntry):
    obses = pressure_block_average_fielddata(geo, dat, userEntry)
    bs, tss = [], []
    for obs in obses:
        b = obs._block_
        t = obs._mtime_
        # print b, t
        if b not in bs:
            bs.append(b)
            tss.append([])
        tss[-1].append(t)

    tbls = lst.history([('e',b,'Pressure') for b in bs])
    if tbls is None:
        raise Exception("Extraction Pressure history of listing results went wrong, blocks: %s" % ','.join(bs))
    # PyTOUGH checks result length, then just return the first set (hence a
    # tuple) if only one in the list, instead of a list
    if not isinstance(tbls, list):
        tbls = [tbls]

    from numpy import interp
    all_obs_vals = []
    for i, (b,ts) in enumerate(zip(bs,tss)):
        alltimes = tbls[i][0] # assuming all times are the same
        allpress = tbls[i][1]
        all_obs_vals += list(interp(ts,alltimes,allpress))

    return all_obs_vals

def pressure_block_average_json_fielddata(geo, dat, userEntry):
    customFilter = userEntry.customFilter
    offsetTime = userEntry.offsetTime
    obsDefault = userEntry.obsDefault
    vFactor, tFactor = 100000.0, 365.25*24.*60.*60.

    # check all required settings exists:
    must_have = ['_DESIRED_DATA_TIMES', '_INTERP_LIMIT', '_P_GRADIENT']
    if any([not hasattr(obsDefault,a) for a in must_have]):
        raise Exception('Obs type pressure_block_average_json must have these default settings: ' + ', '.join(must_have))

    import json
    # 1st line is json file name (of all wells)
    with open(userEntry.obsInfo[0], 'r') as f:
        p_bywell = json.load(f)

    p_byblock = {}

    for oline in userEntry.obsInfo[1:]:
        wname = eval(oline)
        elev = p_bywell[wname]['elevation']

        ts, vs = p_bywell[wname]['times'], p_bywell[wname]['pressures']
        times, vals = [], []
        for time, val in zip(ts, vs):
            if eval(customFilter):
                times.append(time), vals.append(val)

        if len(times) == 0:
            f.close()
            raise Exception("Pressure from %s: %s yields no observation" % (userEntry.obsInfo[0], wname))

        desired_times = obsDefault._DESIRED_DATA_TIMES
        interp_limit = obsDefault._INTERP_LIMIT
        p_gradient = obsDefault._P_GRADIENT

        ##look for the column that contains the bottom of the well
        #for col in geo.columnlist:
        #    #position of well bottom
        #    pos = geo.well[wname].bottom
        #    if col.contains_point(pos):
        #        depth = col.surface - pos[3]
        #
        #geo.column_containing_point(geo.well[wname].bottom)

        # b, bz = calc_bz(geo, wname, pos[3])
        # vals = [p - (bz-pos[3]) * p_gradient for p in vals]

        # correct to block centre
        b, bz = calc_bz(geo, wname, elev)
        vals = [p - (bz-elev) * p_gradient for p in vals]

        # get times and vals for each line (well)
        final_times = [t for t in desired_times if times[0] <= t <= times[-1]]
        final_times = target_times(desired_times, interp_limit, list(zip(times,vals)))
        if len(final_times) == 0:
            msg1 = 'final_times = ' + str(final_times)
            msg2 = 'interp_limit = ' + str(interp_limit)
            msg3 = 'times = ' + str(times)
            msg = "User entry yields no observation: " + oline
            raise Exception('\n'.join([msg1, msg2, msg3, msg]))
        from numpy import interp
        final_vals = list(interp(final_times,times,vals))

        if b not in p_byblock:
            p_byblock[b] = []
        # each block have a list (ts, ps), one for each well in block
        p_byblock[b].append((final_times, final_vals, wname))

    # one series of obs for each block, averaging all these in the same block
    obses = []
    for b in sorted(p_byblock.keys()):
        # fo = open('p_byblock_%s.obs' % b.replace(' ','_'), 'w')
        bp_times = {}
        ws = []
        for dtimes, dvals, wname in p_byblock[b]:
            ws.append(wname)
            for ft,fv in zip(dtimes, dvals):
                if ft not in bp_times:
                    bp_times[ft] = []
                bp_times[ft].append(fv)

        avgt, avgp = [], []
        for t in sorted(bp_times.keys()):
            avgt.append(t)
            avgp.append(sum(bp_times[t]) / len(bp_times[t]))

        from gopest.common import private_cleanup_name
        from copy import deepcopy
        baseName = obsDefault.OBSNME +'_'+ private_cleanup_name(b)
        if baseName not in obsBaseNameCount:
            obsBaseNameCount[baseName] = 0
        for time, val in zip(avgt, avgp):
            obsBaseNameCount[baseName] += 1

            obs = deepcopy(obsDefault)
            obs.OBSNME = baseName +'_'+ ('%04d' % obsBaseNameCount[baseName])
            obs.OBSVAL = val * vFactor
            # additional for model result extraction
            obs._block_ = b
            obs._mtime_ = time * tFactor - offsetTime
            obses.append(obs)
            # output data file in original unit (instead of PEST/TOUGH2)
            # fo.write('%e %e\n' % (time, val))

        # generate batch plot entries
        plot = pressure_plot(
            b, baseName, [t-offsetTime/(60.0*60.0*24.0*365.25) for t in avgt], avgp,
            b+': '+','.join(ws))
        if PLOT_RAW_FIELD_DATA:
            for w in ws:
                ts, vs = p_bywell[w]['times'], p_bywell[w]['pressures']
                plot = plot_append_raw_data(plot, 'raw_'+w, ts, vs, xunit="year", yunit="bar")
        userEntry.batch_plot_entry.append(plot)

        # fo.close()
    return obses

def pressure_block_average_json_modelresult(geo,dat,lst,userEntry):
    obses = pressure_block_average_json_fielddata(geo, dat, userEntry)
    bs, tss = [], []
    for obs in obses:
        b = obs._block_
        t = obs._mtime_
        # print b, t
        if b not in bs:
            bs.append(b)
            tss.append([])
        tss[-1].append(t)

    tbls = lst.history([('e',b,FIELD['pres']) for b in bs])
    if tbls is None:
        raise Exception("Extraction Pressure history of listing results went wrong, blocks: %s" % ','.join(bs))
    # PyTOUGH checks result length, then just return the first set (hence a
    # tuple) if only one in the list, instead of a list
    if not isinstance(tbls, list):
        tbls = [tbls]

    from numpy import interp
    all_obs_vals = []
    for i, (b,ts) in enumerate(zip(bs,tss)):
        alltimes = tbls[i][0] # assuming all times are the same
        allpress = tbls[i][1]
        all_obs_vals += list(interp(ts,alltimes,allpress))

    return all_obs_vals

def private_history_data_with_boiling(userEntry):
    """ A special version of private_history_data() with enthalpy below boiling
    filtered out using user's '_BOILING_ABOVE_ENTH' value.
    """
    # default of 273 degree boiling, J/kg, unit same as internal object unit
    # (same as TOUGH2 unit)
    eboil = 1200.0e3
    if hasattr(userEntry.obsDefault, '_BOILING_ABOVE_ENTH'):
        eboil = userEntry.obsDefault._BOILING_ABOVE_ENTH

    entries = private_history_data(userEntry, 1000.0, 365.25*24.*60.*60.)
    filtered_entries = []
    for o, t in entries:
        if o.OBSVAL >= eboil:
            filtered_entries.append((o,t))
    return filtered_entries

def private_all_blocks_in_geners(name, all_gener_keys):
    """ return a list (unique and sorted) of block names from generators that
    matches name, with regular expression supported.  all_gener_keys should be a
    list of gener keys (tuple of block_name and gener_name).
    """
    import re
    from mulgrids import unfix_blockname,fix_blockname
    pattern = re.compile(name)
    bs = [b for (b,g) in all_gener_keys if pattern.match(unfix_blockname(g)) or pattern.match(g)]
    return sorted(list(set(bs)))

def private_boiling_plot(blockname, gener, datafile, timelist, obsname):
    """ for (timgui) batch plotting """
    return {
        "series": [
            {
                # "type": "HistoryPressureToBoil",
                "type": "HistoryPressureToBoilCO2",
                "block": blockname
            },
            {
                "type": "FrozenDataSeries",
                "name": obsname,
                "original_series": "",
                "frozen_x": list(timelist),
                "frozen_y": [0.0] * len(timelist),
                "xunit": "year",
                "yunit": "pascal",
            }
        ],
        "ylabel": "Pressure Difference to Boil (P-Psat)",
        "xlabel": "Time",
        "title": "%s - %s - %s" % (blockname, gener, datafile)
    }

def boiling_fielddata(geo, dat, userEntry):
    """ called by goPESTobs.py """
    from copy import deepcopy
    from gopest.common import private_cleanup_name
    obsDefault = userEntry.obsDefault

    entries = private_history_data_with_boiling(userEntry)
    if len(entries) == 0:
        raise Exception("User entry yields no observation: " + str(userEntry))

    psat_obses = []
    name = eval(userEntry.obsInfo[0])
    bs = private_all_blocks_in_geners(name, dat.generator.keys())
    if len(bs) == 0:
        msg = 'No GENERs matches with ' + name
        raise Exception(msg + "User entry yields no observation: " + str(userEntry))
    for b in bs:
        baseName = obsDefault.OBSNME +'_'+ private_cleanup_name(b)
        if baseName not in obsBaseNameCount:
            obsBaseNameCount[baseName] = 0
        for o, t in entries:
            obsBaseNameCount[baseName] += 1
            obs = deepcopy(obsDefault)
            obs.OBSNME = baseName +'_'+ ('%04d' % obsBaseNameCount[baseName])
            obs.OBSVAL = 0.0
            psat_obses.append(obs)
        # generate batch plot entries
        userEntry.batch_plot_entry.append(private_boiling_plot(
            b, name, userEntry.obsInfo[1], list(zip(*entries)[1])))
    return psat_obses

def boiling_modelresult(geo, dat, lst, userEntry):
    import numpy as np
    from t2thermo import sat
    from numpy import interp
    obsDefault = userEntry.obsDefault

    entries = private_history_data_with_boiling(userEntry)
    obses, timelist = map(list, zip(*entries))

    name = eval(userEntry.obsInfo[0])
    bs = private_all_blocks_in_geners(name, lst.generation.row_name)
    if len(bs) == 0:
        msg = 'No GENERs matches with ' + name
        raise Exception(msg + "User entry yields no observation: " + str(userEntry))
    selection = []
    for b in bs:
        # print "Boiling Block '%s' from '%s'" % (b, name)
        selection.append(('e',b,FIELD['temp']))
        selection.append(('e',b,FIELD['pres']))
    tbl = lst.history(selection)
    alltimes = tbl[0][0] # assuming all times are the same
    allpdiffs = []
    for i in range(len(bs)):
        ts = tbl[i*2][1]
        ps = tbl[i*2+1][1]
        pdiff_to_boil = []
        for (t,p) in zip(ts,ps):
            pdiff_to_boil.append(p - sat(t))
        pdiffs = interp(timelist,alltimes,np.array(pdiff_to_boil))
        allpdiffs += list(pdiffs)
    return allpdiffs

def private_enthalpy_plot(gname, datafile, timelist, enlist):
    """ for (timgui) batch plotting """
    return {
        "series": [
            {
                "type": "HistoryGenerEnthalpy",
                "gener": gname
            },
            {
                "type": "FrozenDataSeries",
                "name": datafile,
                "original_series": "",
                "frozen_x": [t/(365.25*24.*60.*60.) for t in timelist],
                "frozen_y": enlist,
                "xunit": "t2year",
                "yunit": "kJ/kg", #edited to kj/kg
            }
        ],
        "ylabel": "Average Enthalpy",
        "xlabel": "Time",
        "title": gname
    }

def enthalpy_fielddata(geo,dat,userEntry):
    """ called by goPESTobs.py """
    entries = private_history_data(userEntry, 1000.0, 365.25*24.*60.*60.)
    obses, times = map(list, zip(*entries))
    userEntry.batch_plot_entry.append(private_enthalpy_plot(
        eval(userEntry.obsInfo[0]), userEntry.obsInfo[1], times, [o.OBSVAL for o in obses]))
    return obses
def enthalpy_modelresult(geo,dat,lst,userEntry):
    # name,timelist
    name = eval(userEntry.obsInfo[0])
    entries = private_history_data(userEntry, 1000.0, 365.25*24.*60.*60.)
    obses, timelist = map(list, zip(*entries))
    """
    # nearest value
    import numpy as np
    lst.index = np.abs(lst.fulltimes-time).argmin()
    rows = lst.generation.rows_matching(('',name))
    total_heat, total_mass = 0.0, 0.0
    for r in rows:
        total_mass += r['Generation rate']
        total_heat += r['Generation rate'] * r['Enthalpy']
    if total_mass > 0.0:
        return total_heat / total_mass
    else:
        return 0.0
    """
    import numpy as np
    from mulgrids import unfix_blockname,fix_blockname
    allgs = lst.generation.row_name
    import re
    pattern = re.compile(name)
    gs = [(b,g) for (b,g) in allgs if pattern.match(unfix_blockname(g)) or pattern.match(g)]
    if len(gs) ==0:
        print('Warning, no GENERs matches with ', name)
        return 0.0
    # print "'%s' matches %i geners." % (name, len(gs))
    selection = []
    for gname in gs:
        selection.append(('g',gname,FIELD['rate']))
        selection.append(('g',gname,FIELD['enth']))
    tbl = lst.history(selection)
    alltimes = tbl[0][0] # assuming all times are the same
    total_heat = np.array([0.0 for i in range(len(alltimes))])
    total_mass = np.array([0.0 for i in range(len(alltimes))])
    for i in range(len(gs)):
        total_heat = total_heat + tbl[i*2+1][1] * tbl[i*2][1]
        total_mass = total_mass + tbl[i*2][1]
    average_enth = []
    for (mass,heat) in zip(total_mass,total_heat):
        if abs(mass) <= 1.0e-7:
            average_enth.append(0.0)
        else:
            average_enth.append(heat/mass)
    allenths = np.array(average_enth)
    from numpy import interp
    es = interp(timelist,alltimes,allenths)
    return list(es)

def gradient_by_central(xs, ys):
    import numpy as np
    if type(xs) is not np.ndarray:
        xs = np.array(xs)
    if type(ys) is not np.ndarray:
        ys = np.array(ys)
    z1 = np.hstack((ys[0], ys[:-1]))
    z2 = np.hstack((ys[1:], ys[-1]))

    dx1 = np.hstack((0.0, np.diff(xs)))
    dx2 = np.hstack((np.diff(xs), 0.0))

    d = (z2-z1) / (dx2+dx1)
    return d

def enthalpy_json_fielddata(geo,dat,userEntry):
    """ called by goPESTobs.py """
    jfilename = userEntry.obsInfo[0]
    customFilter = userEntry.customFilter
    offsetTime = userEntry.offsetTime
    obsDefault = userEntry.obsDefault
    vFactor = 1000.0 # assume given J/kg
    tFactor = 365.25*24.*60.*60. # assume given decimal years

    import numpy as np

    def weight_two_ends(def_weight, ends_factor, final_times):
        """ use this to increase or decrease weighting of start/end points in
        history  the middle of the data point will be kept as the set 'WEIGHT',
        then linearly  increases to the specified value here towards two ends.
        It can be either   larger than 1.0 or smaller than 1.0.
        """
        if (final_times[-1] - final_times[0]) < 1.0e-7:
            raise Exception("_ENDS_WEIGHT_FACTOR doesn't work if time range too small")
        final_weights = np.ones(len(final_times)) * def_weight
        half_t_range = (final_times[-1] - final_times[0]) / 2.0
        mid_t = (final_times[-1] + final_times[0]) / 2.0
        for i,t in enumerate(final_times):
            add_fac = abs(t - mid_t) / half_t_range * (ends_factor - 1.0)
            final_weights[i] = final_weights[i] * (add_fac + 1.0)
        return final_weights

    import json
    # 1st line is json file name (of all wells)
    with open(jfilename, 'r') as f:
        e_bywell = json.load(f)

    obses = []

    skipped_entryline = []
    skipped_gradient = []
    for oline in userEntry.obsInfo[1:]:
        wname = eval(oline)
        times, vals = [], []
        for time,val in zip(e_bywell[wname]['times'], e_bywell[wname]['enthalpy']):
            if eval(customFilter):
                times.append(time), vals.append(val)

        if len(times) == 0:
            raise Exception("User entry yields no observation: %s" % wname + str(userEntry))

        if hasattr(obsDefault, '_DESIRED_DATA_TIMES'):
            desired_times = obsDefault._DESIRED_DATA_TIMES
            final_times = [t for t in desired_times if times[0] <= t <= times[-1]]
            if hasattr(obsDefault, '_INTERP_LIMIT'):
                interp_limit = obsDefault._INTERP_LIMIT
                final_times = target_times(desired_times, interp_limit, list(zip(times,vals)))
            if len(final_times) == 0:
                raise Exception("User entry yields no observation: " + str(userEntry))
            from numpy import interp
            final_vals = list(interp(final_times,times,vals))
        else:
            final_times, final_vals = times, vals

        # set this to increase or decrease weighting of start/end points in
        # history the middle of the data point will be kept as the set 'WEIGHT',
        # then linearly increases to the specified value here towards two ends.
        # It can be either larger than 1.0 or smaller than 1.0.
        if hasattr(obsDefault, '_ENDS_WEIGHT_FACTOR'):
            ends_factor = float(obsDefault._ENDS_WEIGHT_FACTOR)
            final_weights = weight_two_ends(obsDefault.WEIGHT, ends_factor, final_times)
        else:
            final_weights = np.ones(len(final_times)) * obsDefault.WEIGHT

        from gopest.common import private_cleanup_name
        baseName = obsDefault.OBSNME +'_'+ private_cleanup_name(wname)[:5]
        if baseName not in obsBaseNameCount:
            obsBaseNameCount[baseName] = 0

        for time, val, w in zip(final_times, final_vals, final_weights):
            obsBaseNameCount[baseName] += 1
            from copy import deepcopy
            obs = deepcopy(obsDefault)
            from gopest.common import private_cleanup_name
            obs.OBSNME = baseName +'_'+ ('%04d' % obsBaseNameCount[baseName])
            obs.OBSVAL = val * vFactor
            obs.WEIGHT = w
            obses.append(obs)

        gpattern = wname
        if hasattr(obsDefault, '_WELL_TO_GENERS'):
            import json
            with open(obsDefault._WELL_TO_GENERS, 'r') as f:
                well_to_geners_dict = json.load(f)
            gpattern = well_to_geners_dict[wname]

        # generate batch plot entries
        plot = enthalpy_plot(
            gpattern, baseName, final_times, final_vals,
            ('Well %s' % wname) )
        if PLOT_RAW_FIELD_DATA:
            ts, vs = e_bywell[wname]['times'], e_bywell[wname]['enthalpy']
            plot = plot_append_raw_data(plot, 'raw_'+wname, ts, vs, xunit="year", yunit="kJ/kg") #edited to kJ/kg
        userEntry.batch_plot_entry.append(plot)

        if hasattr(obsDefault, '_GRADIENT_WEIGHT_FACTOR'):

            w = float(obsDefault._GRADIENT_WEIGHT_FACTOR) * obsDefault.WEIGHT
            if len(final_times) <= 1:
                print('enthalpy_json: User entry has too few data for gradient, skipping: %s' % wname)
                skipped_gradient.append(wname)
                continue
            final_gradients = gradient_by_central(final_times, final_vals)

            baseName = 'g' + obsDefault.OBSNME +'_'+ private_cleanup_name(wname)[:5]
            if baseName not in obsBaseNameCount:
                obsBaseNameCount[baseName] = 0

            for time, grad in zip(final_times, final_gradients):
                obsBaseNameCount[baseName] += 1
                from copy import deepcopy
                obs = deepcopy(obsDefault)
                from gopest.common import private_cleanup_name
                obs.OBGNME = obs.OBGNME + '_g'
                obs.OBSNME = baseName +'_'+ ('%04d' % obsBaseNameCount[baseName])
                obs.OBSVAL = grad
                obs.WEIGHT = w
                obses.append(obs)
    # if skipped_gradient or skipped_entryline:
    #     print('See:\n' + str(userEntry))
    return obses

def private_remove_zeros(times, values):
    import numpy as np
    ts, vs = [],  []
    for t, v in zip(times, values):
        if v != 0.0:
            ts.append(t), vs.append(v)
    return np.array(ts), np.array(vs)

def enthalpy_json_modelresult(geo,dat,lst,userEntry):
    jfilename = userEntry.obsInfo[0]
    customFilter = userEntry.customFilter
    offsetTime = userEntry.offsetTime
    obsDefault = userEntry.obsDefault
    vFactor = 1.0 # assume given J/kg
    tFactor = 365.25*24.*60.*60. # assume given decimal years

    import json
    # 1st line is json file name (of all wells)
    with open(jfilename, 'r') as f:
        e_bywell = json.load(f)

    if hasattr(obsDefault, '_WELL_TO_GENERS'):
        with open(obsDefault._WELL_TO_GENERS, 'r') as f:
            well_to_geners_dict = json.load(f)

    alles = []

    for oline in userEntry.obsInfo[1:]:
        wname = eval(oline)
        times, vals = [], []
        for time,val in zip(e_bywell[wname]['times'], e_bywell[wname]['enthalpy']):
            if eval(customFilter):
                times.append(time), vals.append(val)

        if len(times) == 0:
            raise Exception("User entry yields no observation: " + str(userEntry))

        if hasattr(obsDefault, '_DESIRED_DATA_TIMES'):
            desired_times = obsDefault._DESIRED_DATA_TIMES
            final_times = [t for t in desired_times if times[0] <= t <= times[-1]]
            if hasattr(obsDefault, '_INTERP_LIMIT'):
                interp_limit = obsDefault._INTERP_LIMIT
                final_times = target_times(desired_times, interp_limit, list(zip(times,vals)))
            if len(final_times) == 0:
                raise Exception("User entry yields no observation: " + str(userEntry))
            from numpy import interp
            final_vals = list(interp(final_times,times,vals))
        else:
            final_times, final_vals = times, vals

        import numpy as np
        from mulgrids import unfix_blockname,fix_blockname
        allgs = lst.generation.row_name

        gpattern = wname
        if hasattr(obsDefault, '_WELL_TO_GENERS'):
            gpattern = well_to_geners_dict[wname]

        import re
        pattern = re.compile(gpattern)
        gs = [(b,g) for (b,g) in allgs if pattern.match(unfix_blockname(g)) or pattern.match(g)]
        if len(gs) ==0:
            print('Warning, no GENERs matches with ', gpattern)
            return 0.0
        # print "'%s' matches %i geners." % (wname, len(gs))
        selection = []
        for gname in gs:
            selection.append(('g',gname,FIELD['rate']))
            selection.append(('g',gname,FIELD['enth']))
        tbl = lst.history(selection)
        alltimes = tbl[0][0] # assuming all times are the same
        total_heat = np.array([0.0 for i in range(len(alltimes))])
        total_mass = np.array([0.0 for i in range(len(alltimes))])
        for i in range(len(gs)):
            total_heat = total_heat + tbl[i*2+1][1] * tbl[i*2][1]
            total_mass = total_mass + tbl[i*2][1]
        average_enth = []
        for (mass,heat) in zip(total_mass,total_heat):
            if abs(mass) <= 1.0e-7:
                average_enth.append(0.0)
            else:
                average_enth.append(heat/mass)
        allenths = np.array(average_enth)
        alltimes = alltimes / tFactor + offsetTime / tFactor
        if hasattr(obsDefault, '_REMOVE_ZEROS'):
            if obsDefault._REMOVE_ZEROS:
                alltimes, allenths = private_remove_zeros(alltimes, allenths)
        from numpy import interp
        # print "~~~~~", gpattern, len(final_times), len(alltimes), len(allenths)
        if len(alltimes) == 0:
            es = [0.0] * len(final_times)
            # es = [v - 300.0e3 for v in final_vals]
        else:
            # force enthalpy to be "reasonable", avoid crazy obj fn.
            allenths = [min(3.0e6,max(0.0,enth)) for enth in allenths]
            es = interp(final_times,alltimes,allenths)
        alles = alles + list(es)

        if hasattr(obsDefault, '_GRADIENT_WEIGHT_FACTOR'):
            if len(final_times) <= 1:
                # print('User entry has too few data for gradient, skipping: %s\n%s' % (wname, str(userEntry)))
                continue
            final_gradients = gradient_by_central(final_times, es)
            alles = alles + list(final_gradients)

    return alles

def enthalpy_plot(gname, dataname, ts, es, title):
    """ for (timgui) batch plotting """
    return {
        "series": [
            {
                "type": "HistoryGenerEnthalpy",
                "gener": gname
            },
            {
                "type": "FrozenDataSeries",
                "name": dataname,
                "original_series": "",
                "frozen_x": list(ts),
                "frozen_y": list(es),
                "xunit": "year",
                "yunit": "kJ/kg", #edited to kJ/kg
            }
        ],
        "ylabel": "Average Enthalpy",
        "xlabel": "Time",
        "title": title
    }


def boiling_json_fielddata(geo, dat, userEntry):
    """ called by goPESTobs.py """
    from copy import deepcopy
    from gopest.common import private_cleanup_name
    import json
    import numpy as np

    jfilename = userEntry.obsInfo[0]
    customFilter = userEntry.customFilter
    offsetTime = userEntry.offsetTime
    obsDefault = userEntry.obsDefault
    vFactor = 1.0 # assume given J/kg
    tFactor = 365.25*24.*60.*60. # assume given decimal years

    # default of 273 degree boiling, J/kg, unit same as internal object unit
    # (same as TOUGH2 unit)
    eboil = 1200.0e3
    if hasattr(userEntry.obsDefault, '_BOILING_ABOVE_ENTH'):
        eboil = userEntry.obsDefault._BOILING_ABOVE_ENTH

    # 1st line is json file name (of all wells)
    with open(jfilename, 'r') as f:
        e_bywell = json.load(f)

    obses = []
    boiling_blocks, blk_gener = [], {}

    for oline in userEntry.obsInfo[1:]:
        wname = eval(oline)
        gpattern = wname
        if hasattr(obsDefault, '_WELL_TO_GENERS'):
            import json
            with open(obsDefault._WELL_TO_GENERS, 'r') as f:
                well_to_geners_dict = json.load(f)
            gpattern = well_to_geners_dict[wname]

        times, vals = [], []
        for time,val in zip(e_bywell[wname]['times'], e_bywell[wname]['enthalpy']):
            if eval(customFilter):
                if val >= eboil:
                    times.append(time), vals.append(val)

        if len(times) == 0:
            print(wname, e_bywell[wname]['times'], e_bywell[wname]['enthalpy'])
            raise Exception("User entry has no boiling: " + wname + str(userEntry))
        if hasattr(obsDefault, '_DESIRED_DATA_TIMES'):
            desired_times = obsDefault._DESIRED_DATA_TIMES
            # print wname, desired_times, times, customFilter, e_bywell[wname]['times'], e_bywell[wname]['enthalpy']
            final_times = [t for t in desired_times if times[0] <= t <= times[-1]]
            if hasattr(obsDefault, '_INTERP_LIMIT'):
                interp_limit = obsDefault._INTERP_LIMIT
                final_times = target_times(desired_times, interp_limit, list(zip(times,vals)))
            final_vals = list(np.interp(final_times,times,vals))
        else:
            final_times, final_vals = times, vals
        if len(final_times) == 0:
            raise Exception("User entry yields no observation: " + wname + str(userEntry))

        if isinstance(dat, dict):
            # waiwera JSON input
            gen_keys = [(geo.block_name_list[geo.num_atmosphere_blocks:][gen['cell']], gen['name']) for gen in dat['source']]
        else:
            # aut2 dat
            gen_keys = dat.generator.keys()
        bs = private_all_blocks_in_geners(gpattern, gen_keys)
        if len(bs) == 0:
            print('gen_keys = ' + str(type(dat)) + ' ' + str(gen_keys))
            msg = "Check if dat.filename contains any matching geners:" + gpattern
            msg += "\n           ^^^^^ user entry yields no observation: " + wname + str(userEntry)
            raise Exception(msg)
        for b in bs:
            if b in boiling_blocks:
                msg1 = "block '%s' already used by previous gener '%s'" % (b, blk_gener[b])
                msg2 = "User entry yeilds additional boiling blocks: " + wname + str(userEntry)
                raise Exception('\n'.join([msg2, msg1]))
            blk_gener[b] = wname
            boiling_blocks.append(b)
            baseName = obsDefault.OBSNME +'_'+ private_cleanup_name(b)
            # if baseName not in obsBaseNameCount:
            #     obsBaseNameCount[baseName] = 0
            for time, val in zip(final_times, final_vals):
                # obsBaseNameCount[baseName] += 1
                obs = deepcopy(obsDefault)
                # obs.OBSNME = baseName +'_'+ ('%04d' % obsBaseNameCount[baseName])
                obs.OBSNME = unique_obs_name(obs.OBSNME, b)
                obs.OBSVAL = 0.0
                obs.WEIGHT = obsDefault.WEIGHT
                obs._block_ = b
                obs._mtime_ = time * tFactor - offsetTime
                obses.append(obs)
            # generate batch plot entries
            userEntry.batch_plot_entry.append(private_boiling_plot(
                b, gpattern, wname, final_times, baseName))

    return obses

def boiling_json_modelresult(geo,dat,lst,userEntry):
    from t2thermo import sat
    import numpy as np

    obses = boiling_json_fielddata(geo, dat, userEntry)
    bs, tss = [], []
    for obs in obses:
        b = obs._block_
        t = obs._mtime_
        # print b, t
        if b not in bs:
            bs.append(b)
            tss.append([])
        tss[-1].append(t)

    selection = []
    for b, ts in zip(bs, tss):
        selection.append(('e',b,FIELD['temp']))
        selection.append(('e',b,FIELD['pres']))
        selection.append(('e',b,FIELD['pco2']))

    allpdiffs = []
    tbl = lst.history(selection)
    alltimes = tbl[0][0] # assuming all times are the same
    for i,b in enumerate(bs):
        temps = tbl[i*3][1]
        press = tbl[i*3+1][1]
        pco2 = tbl[i*3+2][1]
        pdiff_to_boil = []
        for (t,p,p2) in zip(temps,press,pco2):
            pd = p - p2 - sat(t)
            if pd < 0.0:
                pd = 0.0 # allow super heating, treated as zero (good)
            pdiff_to_boil.append(pd)
        pdiffs = np.interp(tss[i], alltimes, np.array(pdiff_to_boil))
        allpdiffs += list(pdiffs)

    return allpdiffs


def private_history_data(userEntry,vFactor=1.0,tFactor=1.0):
    """ returns entries of history data read from files.

    If the default obs has (optional) property '_DESIRED_DATA_TIMES', the data
    from field data files will be interpolated into the desired times. The
    purpose of this was to make the observations more uniform in time, use with
    care.  It should be a list of time with the same unit and offset of the data
    files, NOT the rest of PEST/TOUGH2.
    """
    fieldDataFile = userEntry.obsInfo[1]
    customFilter = userEntry.customFilter
    offsetTime = userEntry.offsetTime
    obsDefault = userEntry.obsDefault
    f = open(fieldDataFile,'r')
    fo = open(fieldDataFile+'.obs', 'w')
    times, vals = [], []
    for line in f.readlines():
        if line.strip() == '': break
        time,val = [float(x) for x in line.split()[0:2]]
        if eval(customFilter):
            times.append(time), vals.append(val)

    if len(times) == 0:
        raise Exception("User entry yields no observation: " + str(userEntry))

    if hasattr(obsDefault, '_DESIRED_DATA_TIMES'):
        desired_times = obsDefault._DESIRED_DATA_TIMES
        final_times = [t for t in desired_times if times[0] <= t <= times[-1]]
        if hasattr(obsDefault, '_INTERP_LIMIT'):
            interp_limit = obsDefault._INTERP_LIMIT
            final_times = target_times(desired_times, interp_limit, list(zip(times,vals)))
        if len(final_times) == 0:
            raise Exception("User entry yields no observation: " + str(userEntry))
        from numpy import interp
        final_vals = list(interp(final_times,times,vals))
    else:
        final_times, final_vals = times, vals

    entries = []
    from gopest.common import private_cleanup_name
    baseName = obsDefault.OBSNME +'_'+ private_cleanup_name(userEntry.obsInfo[0])[:5]
    if baseName not in obsBaseNameCount:
        obsBaseNameCount[baseName] = 0
    for time, val in zip(final_times, final_vals):
        obsBaseNameCount[baseName] += 1

        from copy import deepcopy
        obs = deepcopy(obsDefault)
        from gopest.common import private_cleanup_name
        obs.OBSNME = baseName +'_'+ ('%04d' % obsBaseNameCount[baseName])
        obs.OBSVAL = val * vFactor
        entries.append((obs, time * tFactor - offsetTime))
        # output data file in original unit (instead of PEST/TOUGH2)
        fo.write('%e %e\n' % (time, val))
    fo.close()
    f.close()
    return entries


def private_has_re(text):
    """ simplified check of a string contains regular expression or not """
    special = '.^$*+?{}[]()'
    for s in special:
        if s in text:
            return True
    return False
