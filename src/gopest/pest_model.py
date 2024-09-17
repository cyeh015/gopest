""" This is the actual code that wraps TOUGH2 model run with pre- and post-
processing, so all PEST's model/batch file call this.

Use with optiona flags:
    python pest_model.py [--svda] [--obsreref]

Run with "--svda" flag with additional command of parcalc for SVDassist runs.
Flag "--obsreref" is for observation re-referencing which reset save to incon
and overwrites the master's incon, which will be used by all subsequent model
runs.  Flag "--test-update" will cause each slave to save a unique
real_model.save file back to master directory.  This allows "--obsreref" to
later select the best save/incon to start with.

To generate/overwrite/fix the model/batch files, use:
    python make_batch_files.py
"""

import time
import sys
import glob
import os
from os import devnull, system, remove, sep, path
from shutil import copy2
from shutil import Error
from time import sleep

from numpy.testing import assert_approx_equal

from gopest.run_ns_pr import run_ns_pr
from gopest.par import generate_real_model
from gopest.obs import read_from_real_model

from gopest.common import config
from gopest.common import runtime

def get_master_dir():
    if config['mode'] != 'local':
        with open('_master_dir', 'r') as f:
            line = f.readlines()[0].strip()
            return line

def get_pest_dir():
    with open('_pest_dir', 'r') as f:
        line = f.readlines()[0].strip()
        return line

def get_t2():
    with open('_tough2', 'r') as f:
        line = f.readlines()[0].strip()
        return line

def get_slave_id():
    try:
        with open('_procid', 'r') as f:
            line = f.readlines()[0].strip()
            return line
    except:
        return '0'

def par_match(pf1, pf2):
    matched = False
    with open(pf1,'r') as a:
        with open(pf2,'r') as b:
            # once open successfully, assume equal, until something fails
            matched = True
            try:
                for aa,bb in zip(a,b):
                    ax, bx = float(aa.split(',')[0]), float(bb.split(',')[0])
                    assert_approx_equal(ax, bx, significant=7)
            except AssertionError:
                matched = False
    return matched

def main(obsreref, svda, testup, local, skiprun, useobf, sendbad, skippr, hdf5, waiwera):
    fgeo = runtime['filename']['geom']
    fsave = runtime['filename']['save']
    fincon = runtime['filename']['incon']
    fdato = runtime['filename']['dat_orig']
    fdats = runtime['filename']['dat_seq']
    flsts = runtime['filename']['lst_seq']

    print("----- Running " + " ".join(sys.argv[1:]))
    if local:
        master_dir = '.'
    else:
        master_dir = get_master_dir()
    print("--- Clean up pest_model.obf")
    if path.isfile('pest_model.obf'):
        remove('pest_model.obf')

    ### skips everything if use obf directly
    if useobf:
        raise Exception('Should use pest_hp file distribution 17/12/2022')
        if path.isfile('pest_model.obf.use'):
            copy2(master_dir + sep + 'pest_model.obf.use', 'pest_model.obf')
            print("Found pest_model.obf.use , skips everything.")
            return
        else:
            print("Error, cannot find existing pest_model.obf.use file")

    ### SVD-assist
    if svda:
        print("--- PARCALC")
        try:
            remove('pest_model.dat')
        except:
            print("pest_model.dat probably does not exist")
        PARCALC = path.join(get_pest_dir(), 'parcalc')
        system(PARCALC + ' > ' + devnull)

    ### goPESTpar
    if not skiprun:
        print("--- goPESTpar")
        generate_real_model(fdato, 'pest_model.dat', fdats[0])
        # sleep(30)  # just in case shared file system slow

    if obsreref:
        if path.isfile('pest_model.obf'):
            remove('pest_model.obf')
        # get matching incon, if exist
        for parf in glob.glob(master_dir + sep + 'pest_model.dat.*'):
            if par_match(parf, 'pest_model.dat'):
                matchname = path.splitext(parf)[1]
                print("--- found matched incon/pars %s from master dir, overwrite Master INCON" % matchname)
                copy2(master_dir + sep + fincon + matchname, master_dir + sep + fincon)
                copy2(master_dir + sep + 'pest_model.obf' + matchname, 'pest_model.obf')
                break
        # print("--- remove all pairs from labmda tests after searching")
        # for f in glob.glob(master_dir + sep + 'pest_model.obf.*'):
        #     remove(f)
        # for f in glob.glob(master_dir + sep + 'pest_model.dat.*'):
        #     remove(f)
        # for f in glob.glob(master_dir + sep + 'real_model.incon.*'):
        #     remove(f)
        if path.isfile('pest_model.obf'):
            print("--- use obf, skip actual model run")
            return
        else:
            print("--- could not find matching pars, obsreref continue with normal run")

    ### RUN TOUGH2 model
    if skiprun:
        print("--- skip actual TOUGH2 run")
    else:
        if not local:
            print("--- use master INCON")
            try:
                copy2(master_dir + sep + fincon, fincon)
            except Error as e:
                # OK if src and dst are the same file, simply skip.
                print(e)

        START_TIME = time.time()
        print("--- run_ns_pr.py")
        runok = run_ns_pr()
        if obsreref:
            if not local:
                print("--- reset Master INCON")
                copy2('real_model.incon', master_dir + sep + 'real_model.incon')
            else:
                print("--- .save file written as .incon")
        if sendbad:
            for f in glob.glob('bad_model_*'):
                copy2(f, master_dir + sep + 'bad_model_slave' + get_slave_id() + '_' + f)
        if not runok:
            print("--- run_ns_pr failed, skip goPESTobs, no obf, make sure lamforgive/derforgive is used.")
            return
        print('--- run_ns_pr complete after', (time.time() - START_TIME), 'seconds')

    ### goPESTobs
    # sleep(30)  # just in case shared file system slow
    print("--- goPESTobs")
    read_from_real_model(fgeo, fdats[-1], flsts[-1], 'pest_model.obf', waiwera=waiwera)

    if testup:
        print("--- store lambda test (save,obf,pars) pair:" + get_slave_id())
        copy2(fsave, master_dir + sep + fincon + '.' + get_slave_id())
        copy2('pest_model.dat', master_dir + sep + 'pest_model.dat.' + get_slave_id())
        copy2('pest_model.obf', master_dir + sep + 'pest_model.obf.' + get_slave_id())

def main_cli(argv=[]):
    obsreref = False
    svda = False
    testup = False
    skiprun = False
    useobf = False
    sendbad = True
    skippr = False
    waiwera = False
    hdf5 = False

    if config['simulator']['output-type'] == 'h5':
        hdf5 = True
    else:
        hdf5 = False
    
    if config['simulator']['input-type'] == 'waiwera':
        waiwera = True
        hdf5 = True
    else:
        waiwera = False

    local = config['mode'] == 'local'
    skiprun = config['model']['skip']
    skippr = config['model']['skip-pr']

    print('pest_model.py running at ', os.getcwd())
    
    if len(argv) > 1:
        if '--test-update' in argv[1:]:
            testup = True
        if '--obsreref' in argv[1:]:
            obsreref = True
        if '--svda' in argv[1:]:
            svda = True
        if '--use-obf' in argv[1:]:
            # requires existing pest_model.obf.use (PEST will remove
            # pest_model.obf, so use different name)
            useobf = True
        if '--local' in argv[1:]:
            local = True
    main(obsreref, svda, testup, local, skiprun, useobf, sendbad, skippr, hdf5, waiwera)
