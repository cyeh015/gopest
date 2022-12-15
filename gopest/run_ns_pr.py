from mulgrids import *
from t2data import *
from t2listing import *
from t2incons import *
import h5py
import gener_groups
import sys
import os
import time
import re
import json
import numpy as np
import tarfile
from shutil import copy2, move
from time import sleep
import subprocess

def tail(filename, n=10):
    """ Return the last n lines of a file """
    from collections import deque
    return deque(open(filename), n)

def read_gener_file(fname):
    f = t2data_parser(fname,'rU')
    line = f.readline()
    if line[:5] != 'GENER':
        # get rid of first line 'GENER' and check
        raise Exception("File %s is not a valid generator file, must starts with GENER." % fname)
    gs = t2data()
    gs.read_generators(f)
    f.close()
    return gs.generatorlist

def read_cols_in_zones(geo, fname='real_model.json'):
    """
    NOTE WIP, need to deal with zone order in some cases (one zone includes another)
    """
    with open(fname, 'rU') as jf:
        cfg = json.load(jf)
        col_zone = {}
        for zone in cfg['ZonePolygon'].keys():
            zone_polygon = [np.array(pt) for pt in cfg['ZonePolygon'][zone]]
            for c in geo.columns_in_polygon(zone_polygon):
                col_zone[c.name] = zone
    return col_zone

def save_bad_model(dat, sav):
    """ keep a model and its incon aside for later inspection, iused in the
    case of difficult to converge.
    """
    archive_dir = 'bad_models'
    def next_unused_dir():
        from os.path import isdir, isfile, join
        i = 1
        p = join(archive_dir, str(i))
        while isdir(p) or isfile(p):
            i += 1
            p = join(archive_dir, str(i))
        return p
    psave = next_unused_dir()
    os.makedirs(psave)
    dat.write(psave + os.sep + 'real_model.dat')
    sav.write(psave + os.sep + 'real_model.incon')

def targz_files(files, default_name):
    """ add files into a compressed tar file (.tar.gz).  File name will be
    default_name with a number.  The number will be incremented if other tar
    file existed based on the same name.
    """
    i = 1
    f = default_name + str(i) + ".tar.gz"
    while os.path.isfile(f):
        i += 1
        f = default_name + str(i) + ".tar.gz"
    tar = tarfile.open(f, 'w:gz')
    for name in files:
        if os.path.isfile(name) or os.path.isdir(name):
            tar.add(name)
    tar.close()
    return f

def fix_base_heat(dat, geo):
    fname = 'real_model.json'
    col_zone = read_cols_in_zones(geo, fname=fname)
    with open(fname, 'r') as jf:
        cfg = json.load(jf)
    for g in dat.generatorlist:
        if g.name.endswith('99') and g.type == 'HEAT':
            col = geo.column[geo.column_name(g.block)]
            if col.name in col_zone:
                v = cfg['HeatFlux'][col_zone[col.name]]
            else:
                v = cfg['HeatFlux']['Default']
            g.gx = col.area * v
    return dat

def fix_co2_mass_ratio(dat):
    # ohaaki seems to use 4%, have not checked with Mike yet
    # CO2_MASS_RATIO = 0.04
    with open('data_co2_ratio.json', 'r') as f:
        ratio = json.load(f)
    mass = {}
    for g in dat.generatorlist:
        if g.block.endswith('61') and g.name.endswith('77') and g.type == 'MASS':
            mass[g.block] = g.gx
    for g in dat.generatorlist:
        if g.block.endswith('61') and g.name.endswith('66') and g.type == 'COM2':
            # g.gx = mass[g.block] * CO2_MASS_RATIO
            g.gx = mass[g.block] * ratio[g.block]
    return dat

def set_output_times(dat, print_every=31558000.0):
    """ a year is actually 31557600 sec, but precision will be lost, so it would
    be 31558000 that actually used. """
    dat.output_times.update({
        'max_timestep': 0.0,
        'num_times': 1000,
        'num_times_specified': 1,
        'time': [print_every],
        'time_increment': print_every,
        })
    dat.parameter.update({
        'max_timesteps': -999, # unlimited
        'print_interval': -999, # do not print with MCYPR
        })
    dat.parameter['option'][24] = 2
    dat.parameter['option'][16] = 5
    return dat

def ensure_converge(ns, sav, allow_failed_ns=True):
    # re-run until taget time reached, max 3 times.
    from os.path import splitext
    datbase,ext = splitext(ns.filename)
    target_ns_time = ns.parameter['tstop']
    run = 0
    while abs(sav.timing['sumtim'] - target_ns_time) > 1000 and run < 0:
        run += 1
        print('Warning NS ends at %e sec, did not reach target time: %e, re-run NS for %ith time.' % (float(sav.timing['sumtim']), float(target_ns_time), run))
        ns.write(datbase+"_rerun.dat", echo_extra_precision=True)
        sav.write(datbase+"_rerun.incon", reset=True)
        ns.run(simulator=simulator, silent=silent)
        sav = t2incon(datbase+"_rerun.save")
    if abs(sav.timing['sumtim'] - target_ns_time) > 1000:
        print('Warning NS ends at %e sec, still not reach target time: %e, after %ith tries.' % (float(sav.timing['sumtim']), float(target_ns_time), run))
        tfname = targz_files([datbase+'.dat', datbase+'.pdat', datbase+'.incon'],
            'bad_model_')
        print(tfname, 'saved')
        if not allow_failed_ns:
            return False
    return sav

def run_ns_pr(skippr=False, save2inc=False, simulator='waiwera-dkr',
              allow_failed_ns=True, silent=True):
    """ convert aut2 model into waiwera, and run ns/pr

    supported platforms:
        'waiwera' - local native waiwera executable
        'waiwera-dkr' - local waiwera running on docker
        'waiwera-Maui' - NeSI Maui (uses submit_beopest.py)
        'waiwera-Mahuika' - NeSI Mahuika (uses submit_beopest.py)
    """
    geo = mulgrid("g_real_model.dat")
    inc = t2incon("real_model.incon")
    inc.porosity = None
    inc.write("real_model.incon", reset=True)
    inc = t2incon("real_model.incon")
    t2_ns = t2data("real_model.dat")
    t2_ns = fix_co2_mass_ratio(t2_ns)
    t2_ns.write(echo_extra_precision=True)

    if os.path.exists('real_model.incon.h5'):
        # check incon
        inc_h5 = h5py.File('real_model.incon.h5', 'r')
        inc_idx = len(inc_h5['time'][:,0]) - 1
        if inc_idx < 0:
            raise Exception("ERROR! Waiwera initial conditions file 'real_model.incon.h5' has no data.")
        inc_h5.close()
        use_inc = '--' # use dummy in dat.json(), then replaced later
    else:
        print('real_model.incon.h5 does not exist, use T2 real_model.incon instead.')
        use_inc = inc

    wai_ns = t2_ns.json(geo, 'g_real_model.msh',
                     atmos_volume=1.e25,
                     incons=use_inc,
                     eos=None,
                     bdy_incons=inc, # somehow I still need it to avoid error
                     mesh_coords='xyz')

    wai_ns_orig = json.load(open('real_model_original.json', 'r'))
    for k in ["time", "output", "mesh"]:
        wai_ns[k] = wai_ns_orig[k]

    # overwrite these just to be safe
    wai_ns["thermodynamics"] = {"name": "ifc67", "extrapolate": True}
    wai_ns["output"]["filename"] = "real_model.h5"
    wai_ns["output"]["frequency"] = 1000
    wai_ns["time"]["step"]["maximum"]["number"] = 80000
    wai_ns["time"]["stop"] = 0.5e14
    wai_ns["mesh"]["filename"] = "g_real_model.msh"
    if use_inc == '--':
       wai_ns["initial"] = {"filename": "real_model.incon.h5", "index": inc_idx}

    json.dump(wai_ns, open('real_model.json', 'w'), indent=2, sort_keys=True)

    # clean up
    clean_files = [
        'real_model.h5',
        'real_model.save',
        'real_model.listing',
    ]
    for cf in clean_files:
        try:
            os.remove(cf)
        except OSError:
            pass
    model_cmd = [
        'real_model.json',
        '-ksp_type', 'bcgsl',
        '-snes_ksp_ew',
        '-snes_ksp_ew_rtol0', '1e-5',
        '-snes_ksp_ew_rtolmax', '1e-4',
        '-pc_type', 'asm',
        '-pc_factor_levels', '1',
        '-snes_max_linear_solve_fail', '3',
        ]
    NP = 4
    cmd = {
        'waiwera': ['mpiexec', '-np', str(NP), 'waiwera', '-np'] + model_cmd,
        'waiwera-dkr': ['waiwera-dkr', '-np', str(NP), '--tag', 'testing'] + model_cmd,
        'waiwera-Maui': ['python', 'submit_beopest.py', '--forward3maui', ' '.join(['~/bin/waiwera-maui']+model_cmd)],
        'waiwera-Mahuika': ['python', 'submit_beopest.py', '--forward3mahuika', ' '.join(['~/bin-mahuika/waiwera']+model_cmd)],
    }[simulator]
    START_TIME = time.time()
    print('NS launched on %s...' % simulator)
    # run NS
    print(cmd)
    subprocess.call(cmd)

    # check NS
    if os.path.exists('real_model.h5'):
        inc_h5 = h5py.File('real_model.h5', 'r')
        inc_idx = len(inc_h5['time'][:,0]) - 1
        if inc_idx < 0:
            raise Exception("ERROR! output file 'real_model.h5' has no data.")
        endtime = inc_h5['time'][inc_idx, 0]
        inc_h5.close()
        if abs(endtime - wai_ns['time']['stop']) < 1.e3:
            print('NS finished after %.1f seconds' % (time.time() - START_TIME))
        else:
            print('NS failed after %.1f seconds' % (time.time() - START_TIME))
            if not allow_failed_ns:
                return False

    if skippr:
        copy2('real_model.h5', 'real_model_pr.h5')
        msg = 'Skipped PR, use NS result as PR for goPESTobs/pest_model'
        print(msg)
        return True

    # change NS to PR
    wai_pr = wai_ns
    with open('gs_production.json', 'r') as f:
        data = json.load(f)
        wai_pr['source'] = wai_pr['source'] + data
    with open('real_model_pr.output.json', 'r') as f:
        data = json.load(f)
        wai_pr['output'] = data
    with open('real_model_pr.time.json', 'r') as f:
        data = json.load(f)
        wai_pr['time'] = data
    # additional
    wai_pr['output']['filename'] = 'real_model_pr.h5'
    wai_pr['output']['frequency'] = 0
    wai_pr["initial"] = {"filename": "real_model.h5", "index": inc_idx}

    json.dump(wai_pr, open('real_model_pr.json', 'w'), indent=2, sort_keys=True)

    # clean up
    clean_files = [
        'real_model_pr.h5',
        'real_model_pr.save',
        'real_model_pr.listing',
    ]
    for cf in clean_files:
        try:
            os.remove(cf)
        except OSError:
            pass
    START_TIME = time.time()
    print('PR launched on %s...' % simulator)
    model_cmd = [
        'real_model_pr.json',
        '-ksp_type', 'bcgsl',
        '-snes_ksp_ew',
        '-snes_ksp_ew_rtol0', '1e-5',
        '-snes_ksp_ew_rtolmax', '1e-4',
        '-pc_type', 'asm',
        '-pc_factor_levels', '1',
        '-snes_max_linear_solve_fail', '3',
        ]
    NP = 4
    cmd = {
        'waiwera': ['mpiexec', '-np', str(NP), 'waiwera', '-np'] + model_cmd,
        'waiwera-dkr': ['waiwera-dkr', '-np', str(NP), '--tag', 'testing'] + model_cmd,
        'waiwera-Maui': ['python', 'submit_beopest.py', '--forward3maui', ' '.join(['~/bin/waiwera-maui']+model_cmd)],
        'waiwera-Mahuika': ['python', 'submit_beopest.py', '--forward3mahuika', ' '.join(['~/bin-mahuika/waiwera']+model_cmd)],
    }[simulator]
    # run
    print('Running PR ...')
    print(cmd)
    START_TIME = time.time()
    subprocess.call(cmd)

    # check PR
    if os.path.exists('real_model_pr.h5'):
        inc_h5 = h5py.File('real_model_pr.h5', 'r')
        inc_idx = len(inc_h5['time'][:,0]) - 1
        if inc_idx < 0:
            raise Exception("ERROR! output file 'real_model.h5' has no data.")
        endtime = inc_h5['time'][inc_idx, 0]
        inc_h5.close()
        if abs(endtime - wai_pr['time']['stop']) < 1.e3:
            print('PR finished after %.1f seconds' % (time.time() - START_TIME))
        else:
            print('PR failed after %.1f seconds' % (time.time() - START_TIME))
            if not allow_failed_ns:
                return False
    # fake a dummy real_model_pr.dat (for goPESTobs.py), need to check not used by those obs types
    t2_ns.write('real_model_pr.dat', echo_extra_precision=True)
    return True

def run_ns_pr_aut2(skippr=False, save2inc=False, simulator='AUTOUGH2_3D',
                   allow_failed_ns=True, silent=True):
    geo = mulgrid("g_real_model.dat")
    inc = t2incon("real_model.incon")
    inc.porosity = None
    inc.write("real_model.incon", reset=True)
    inc = t2incon("real_model.incon")
    ns = t2data("real_model.dat")
    ns = fix_co2_mass_ratio(ns)
    ns.write(echo_extra_precision=True)

    START_TIME = time.time()
    ns.run(simulator=simulator, silent=silent)
    sav = t2incon("real_model.save")
    sav = ensure_converge(ns, sav, allow_failed_ns)
    print('NS finished after ', (time.time() - START_TIME), 'seconds')
    if sav is False:
        return False
    if save2inc:
        sav.write("real_model.incon", reset=True)

    if skippr:
        # fake real_model_pr.* because thats what pest_model.py will apply goPESTobs on
        copy2('real_model.dat', 'real_model_pr.dat')
        copy2('real_model.pdat', 'real_model_pr.pdat')
        copy2('real_model.listing', 'real_model_pr.listing')
        msg = 'Skipped PR, make sure to use NS result as PR for goPESTobs/pest_model'
        print(msg)
        return True

    ##### everything below is production run
    pr = t2data("real_model_original_pr.dat")
    target_pr_time = pr.parameter['tstop']
    # pr = set_output_times(pr, 15779000.0) # every half year
    pr = set_output_times(pr, 31558000.0) # every year

    pr.grid = ns.grid
    pr.clear_generators()
    for g in ns.generatorlist:
        pr.add_generator(g)
    # Append all additinal generators at the end
    gs_to_add = read_gener_file('production.geners')
    for g in gs_to_add:
        pr.add_generator(g)

    pr.write("real_model_pr.dat", echo_extra_precision=True)
    sav.write("real_model_pr.incon", reset=True)

    print('Running PR ...')
    START_TIME = time.time()
    pr.run(simulator=simulator, silent=silent)
    print('PR finished after ', (time.time() - START_TIME), 'seconds')

    prsav = t2incon("real_model_pr.save")
    if abs(prsav.timing['sumtim'] - target_pr_time) > 1000:
        print('Warning PR ends at %e sec, did not reach target time: %e' % (float(prsav.timing['sumtim']), float(target_pr_time)))
        print(''.join([line for line in tail('real_model_pr.listing', n=20)]))

    return True

def get_t2():
    with open('_tough2', 'r') as f:
        line = f.readlines()[0].strip()
        return line

def main_cli(argv=[]):
    skippr = False
    sav2inc = False

    if len(argv) > 1:
        if '--skip-pr' in argv[1:]:
            skippr = True
        if '--sav2inc' in argv[1:]:
            sav2inc = True
    run_ns_pr(skippr, sav2inc, simulator=get_t2(), silent=True)
