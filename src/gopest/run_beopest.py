import os
import sys
import shutil
import time
import json
from subprocess import Popen, DEVNULL
from multiprocessing import cpu_count

from gopest.common import config as cfg
from gopest.common import runtime

NUM_SLAVES = cfg['pest']['num_slaves']
SILENT_SLAVES = cfg['pest']['silent_slaves']
PST_NAME = cfg['pest']['case-name']
PORT = cfg['pest']['port']
SWITCHES = " ".join(cfg['pest']['switches'])

TOUGH2 = cfg['simulator']['executable']
BEOPEST = cfg['pest']['executable']
PESTDIR = cfg['pest']['dir']

"""
This script helps to launch BeoPEST on the case in current directory (either
'case.pst' or 'case_svda.pst').  Use:

    python run_beopest.py

Requires:
    - Python 2.6 or 2.7, NumPy
    - PEST and TOUGH2 executables, see settings above.

Most of the important settings are listed above.  Instead of letting PEST runs
TOUGH2 models directly, actual model runs were controlled by the pest_model.py
script, which uses the goPEST interface and run_ns_pr.py.  (goPEST is a little
like PLPROC)

In the actual workflow, there are only a couple files that need attention:

    - goPESTpar.list    a list of parameters (goPESTpar.py translates this into
        actual PEST parameter data)
    - goPESTobs.list    a list of observations (goPESTobs.py translates this
        into actual PEST observation data)

Brief workflow:

    1. edit goPESTpar.list and goPESTobs.list

    2. run 'python make_case_pst.py', which processed two lists above and
    updates case.pst.  This also initialise the parameter values from the values
    in the real_model_original.dat (.pdat).

    3. inspect/modify/check case.pst

    4. run 'python run_beopest.py'

    5. to obtain the model with optimised parameters run 'python
    make_real_model.py' or 'python make_real_model_svda.py', now
    real_model.dat is the updated model, run_ns_pr.py can be used to run    this
    model.

    6. occasionally run 'make_batch_files.py', eg. after svdaprep, so that model
    batch files are correct.  This should be run after moving the folder between
    platform as well.

To update/change a TOUGH2 model, the following files needs to be updated:

    - g_real_model.dat (model's mulgrid/geometry file)
    - real_model_original.dat (and .pdat)
    - real_model_original_pr.dat (and .pdat, rocktypes, geners not as important,
        they are processed from the natural state real_model_ogirinal.dat)
    - real_model.incon
    - and of course goPESTpar.list and goPESTobs.list
    - make sure to run 'python make_case_pst.py'

"""

if NUM_SLAVES is None:
    NUM_SLAVES = max(cpu_count() - 2, 1)
if PESTDIR:
    BEOPEST = os.path.join(PESTDIR,BEOPEST)

def ignore_dirs(folder, files):
    """ for shutil.copytree, ignores all subdirectories, ie. copy only files
    """
    ignore_list = []
    for f in files:
        full_path = os.path.join(folder, f)
        if os.path.isdir(full_path):
            ignore_list.append(f)
    return ignore_list

def run_cli(argv=[]):
    """ generate master and slave commands, copy files into slave directories,
    and launch them as process, wait until all finished.
    """

    if "pest_hp" in BEOPEST.lower():
        MASTER = BEOPEST
        if PESTDIR:
            AGENT = os.path.join(PESTDIR, cfg['pest']['executable_agent'])
        else:
            AGENT = cfg['pest']['executable_agent']
    else:
        MASTER = BEOPEST
        AGENT = BEOPEST

    generate_comm_files()
    print('Running BeoPEST with silent=', SILENT_SLAVES)

    # each command is a tuple (args, other options), see subproces.Popen()
    master = ([MASTER, PST_NAME, SWITCHES, '/h :%s' % PORT], {} )
    slaves, slaves_outs = [], []
    for i in range(NUM_SLAVES):
        s_dir = 'slave%i' % (i+1)
        if os.path.exists(s_dir):
            shutil.rmtree(s_dir)
        shutil.copytree('.', s_dir, ignore=ignore_dirs)
        if SILENT_SLAVES:
            # stdout_file = DEVNULL
            stdout_file = open(s_dir + '/stdout.txt', 'w')
            slaves_outs.append(stdout_file)
        else:
            stdout_file = None
        slaves.append((
            [AGENT, PST_NAME, '/h localhost:%s' % PORT],
            {
                'cwd': s_dir,
                'stdout': stdout_file,
                'stderr': stdout_file,
            }))

    # start master, sleep a bit, then start all slaves
    ps = []
    ps.append(Popen(master[0], **master[1]))
    time.sleep(0.1)
    for s in slaves:
        ps.append(Popen(s[0], **s[1]))
    for p in ps:
        p.wait()
    for f in slaves_outs:
        f.close()

def gen_run_management_file(nslave, slaves, wait=0.2, parlam=1, runtime=3600):
    """ generate run management file required by ppest/jactest.  I am
    implementing the simplified version here, single template and instruction
    file only.  TODO extend to be more flexible, which may require more info
    from pest control file.  Each slaves is a list of tuple (SLAVNAME,SLAVDIR),
    should have the same length as nslaves.
    """
    ifletyp = 0 # for now
    lines = []
    lines += [
        'prf',
        '%i %i %f %i' % (nslave, ifletyp, wait, parlam),
    ]
    for i in range(nslave):
        slavname, slavdir = slaves[i]
        if " " in slavname or "'" in slavname:
            slavname = slavname.replace("'", "''")
            slavname = "'" + slavname + "'"
        lines.append(slavname + ' ' + slavdir)
    lines.append(' '.join([str(runtime)] * nslave))
    # TODO: support non-zero IFLETYP
    return '\n'.join(lines)

def run_pslaves(master_command):
    """ generate master and slave commands, copy files into slave directories,
    and launch them as process, wait until all finished.  master_command should
    be a list of strings [cmd, arg1, arg2, ...].
    """
    # each command is a tuple (args, other options), see subproces.Popen()
    master = (master_command, {} )
    slaves = []
    for i in range(NUM_SLAVES):
        s_dir = 'slave%i' % (i+1)
        if os.path.exists(s_dir):
            shutil.rmtree(s_dir)
        shutil.copytree('.', s_dir, ignore=ignore_dirs)
        slaves.append((
            [BEOPEST, PST_NAME, '/h localhost:%s' % PORT],
            {
                'cwd': s_dir,
            }))

    # start master, sleep a bit, then start all slaves
    ps = []
    ps.append(Popen(master[0], **master[1]))
    time.sleep(0.1)
    for s in slaves:
        ps.append(Popen(s[0], **s[1]))
    for p in ps:
        p.wait()

def generate_comm_files():
    """ generate some files contain information so slaves know where things are.
    TODO: to improve, there should be better ways, partially to fit with my
    original NeSI system.
    """
    def write_to(filename, line):
        with open(filename, 'w') as f:
            f.write(line)
    write_to('_master_dir', os.getcwd())
    write_to('_pest_dir', PESTDIR)
    if isinstance(TOUGH2, list):
        write_to('_tough2', ' '.join(TOUGH2))
    else:
        write_to('_tough2', TOUGH2)
    with open('_gopest.json', 'w') as f:
        json.dump({
            'master_dir': os.getcwd(),
            'pest_dir': PESTDIR,
            'tough2': TOUGH2,
            'mode': 'local'
            }, f, indent=2)

if __name__ == '__main__':
    run_cli()
