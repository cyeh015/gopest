#!/bin/python

import os
import subprocess

from gopest.common import config as cfg
from gopest.common import runtime

"""
Run this script to submit BeoPEST jobs on NeSI using Slurm.  This includes
master and slaves jobs.  Note the BeoPEST here uses TCP communication.

1. Modify the following paragraph of settings.
2. Set up PEST directory properly.
3. Run "python submit_beopest.py" from the main PEST directory.

Angus Yeh
a.yeh@auckland.ac.nz
June 2015
"""

PROJECT = cfg['nesi']['project']
PROJECT_MAUI = cfg['nesi']['maui']['project']
PROJECT_MAHUIKA = cfg['nesi']['mahuika']['project']

WALLTIME_MASTER = cfg['nesi']['walltime_master']
WALLTIME_SLAVES = WALLTIME_MASTER

WALLTIME_FORWARD = cfg['nesi']['walltime_forward']

MAUI_NTASKS = cfg['nesi']['maui']['ntasks']
MAHUIKA_NTASKS = cfg['nesi']['mahuika']['ntasks']

NUM_SLAVES = cfg['pest']['num_slaves']

MEM_PER_SLAVE = "5000" # MB
MEM_MASTER = "500"
MEM_FORWARD = "4000"

# SIMULATOR = "~/bin/autough2_6b" # specify absolute path if not in system path
# SIMULATOR = "waiwera-Mahuika" # specify absolute path if not in system path
# 'waiwera': local native waiwera, installed in path
# 'waiwera-dkr': running locally using Docker with pywaiwera installed
# 'waiwera-Maui': calling submit_beopest.py and use Maui
# 'waiwera-Mahuika': calling submit_beopest.py and use Mahuika
SIMULATOR = cfg['simulator']['executable']

PST_NAME = cfg['pest']['case-name']
PESTDIR = cfg['pest']['dir']
SLAVEDIR = cfg['pest']['slave_dirs']
BEOPEST = cfg['pest']['executable']
PORT = cfg['pest']['port']

SWITCHES = " ".join(cfg['pest']['switches'])
# additional swiches for beopest, eg /s for restart, /p1 for parallise 1st model run
# should not use /p1 with svda, no /p1 with obsreref_10 either
# /hpstart, make sure PST_NAME.hp exists
# /i jco reuse, make sure PST_NAME.jco exists
# NOTE it's possible to use /hpstart and /i together, will start update tests right away
# NOTE working directory is assumed to be where this script is launched

# if use /f, PEST_HP runs a sets of forward runs using .par files
F_PAR_SETS = ["prandom", "11", "50", "40", PST_NAME+".rrf"]
# Enter filename base of parameter value files:
# Enter first index to use:
# Enter last index to use:
# Enter parallel run packet size:
# Enter name for run results file:

# used for slurm to redirect as standard input
use_input = False
with open('_input', 'w') as f:
    # if PEST_HP asks name of jacobian file, then use file named PST_NAME + ".jco"
    if "/i" in SWITCHES:
        f.write(PST_NAME + ".jco\n")
        use_input = True
    if "/f" in SWITCHES:
        f.write("\n".join(F_PAR_SETS))
        use_input = True

SLAVES_ON_SCRATCH = False
KEEP_TARGZ_SLAVES = False
# normally when a slave ends, the slave directory will be tar-gz-ed for debugging
# but this can be huge due to TOUGH2 listing files, these files can be summarised
# (using head and tail) to save space
SUMMARY_LARGE_FILES = "" #"*.listing"

MAIN_DIR = os.getcwd()

# use absolute path if known
if PESTDIR:
    BEOPEST = os.path.join(PESTDIR,BEOPEST)

# list NeSI modules that needs to load for running scripts/AUTOUGH2 etc.
ENV_MODULES = [
    'module load gimkl/2018b',
    'module load Python-Geo/3.7.3-gimkl-2018b',
    'source /nesi/project/uoa00124/env-py3-gopest/bin/activate',
    # 18/12/2022 3:34:08 a.m.
    # # "module GCC/4.9.2",
    # # "module Python/2.7.11-foss-2015a",
    # "module load gimkl/2017a",
    # "module load GCC/7.1.0",
    # "module load Python-Geo/2.7.14-gimkl-2017a",
]
# user can load these modules by command 'source _load_modules.sh'
with open('_load_modules.sh', 'w') as f:
    f.write('\n'.join([
        "echo !!! Please source this file to modify environment in calling shell",
        "echo \"    'source _load_modules.sh'\"",
        ] + ENV_MODULES))

ENV_MODULES_MAUI = cfg['nesi']['maui']['env_init']
ENV_MODULES_MAHUIKA = cfg['nesi']['mahuika']['env_init']

# communication files:
# pest files
# goPEST*
# pest_model*
# real_model*       (from gopest.common.runtime)
# data_*            (from toml)
# gs_*              (from toml)


pst_name = cfg['pest']['case-name']
slave_files = [
    pst_name + '.pst',
    # communication files:
    "_input",
    "_pest_dir",
    "_tough2",
    "_logfile",
    "_master_out",
    # goPEST working files
    "pest_model.ins",
    "pest_model.tpl",
    "goPESTconfig.toml",
    "goPESTpar.list",
    "goPESTobs.list",
    # user supplied function, may not exist
    "goPESTuser.py",
]
# forward run files -> generated from toml
slave_files += [
    # runtime['filename']['save'],
    runtime['filename']['incon'],
    runtime['filename']['dat_orig'],
]
slave_files += runtime['filename']['all_geoms']
slave_files += runtime['filename']['dat_seq']
# slave_files += runtime['filename']['lst_seq']
# user files -> copied from toml
slave_files += cfg['files']['slave']

master_files = slave_files
if "/hpstart" in cfg['pest']['switches']:
    master_files.append(pst_name + '.hp')
if "/i" in cfg['pest']['switches']:
    master_files.append(pst_name + '.jco')

master_files += cfg['files']['master']

# All files needed in slave directory
# TODO: should have both master_files and slave_files
FILE_LIST = " ".join(slave_files)

"""
Details
-------

This explains the working solution of using BeoPEST on NeSI, which is
implemented by this script.

This version of BeoPEST works uses TCP, MPI not supported with some SVD stuff
John Doherty added (11/12/2014).

Slurm job files generated for submission:

    _master_job.sl   -> this is job file for launching master beopest along with
                        a set of slaves, using N+1 cpus
    _slaves_job.sl   -> job file for slaves, using N cpus
    _multi.conf      -> used by slaves job file, calls _run_a_slave.sh
    _run_master.sh   -> record which host it is running on, run master beopest
    _run_a_slave.sh  -> copy required files to unique slave directories, then
                        launch single beopest in slave mode.

    _master_dir      -> so slave jobs know where master directory is
    _master_out      -> so slave jobs know where to print information
    _pest_dir        -> so slaves know where to find PEST/BeoPEST utilities
    _tough2          -> so slaves know which SIMULATOR simulator to use

This set of scripts/job files basically launch a beopest as master in the main
directory by calling:

    beopest case /h :4004

In the master job file, a command is used to detect which host it is run on. The
info is saved to a file _master_host in the main direcotry.  Hence the slaves
are set to run with a small delay, to ensure the existence _master_host file.

Now a sbatch --dependency after:JOB_ID is used to launch slaves.  Note it's
after: not afterok: as seen in the examples.  This runs the slaves after master
STARTED (instead of finished).

The slaves job file uses srun --multi-prog, which reads _multi.conf file that
tells how to launch each slave.  Each slave is launched by using a bash script.
The script includes the code to:
    1. create unique slave dir, and copy required files
    2. change directory
    3. obtain the hostname of master beopest (from file _master_host)
    4. launch beopest case /h masterhost:4004

Also something bad might happen if more than one BeoPEST master uses the same
communication port.  So it's a good idea to set PORT to something different
when you receive this script.  Usually some large number is okay.

Tips For Users
--------------
    - You can launch more slave jobs by copy commands shown on screen after
      submission.  Note the dependency jobid is important.
    - Job ids are shown on the screen, you can cencel jobs by "scancel JOBID"
    - cleanups can be done by:
          rm -r slave_*
          rm *.out
          rm _*
      (be carefule not to delete your own files, if they match the names here.)
    - On linux, you have to change a script into an 'executable' if you want to
      run it directly like "./myscript.sh", instead of "bash myscript.sh".
      This requires you to issue the command:
          chmod +x myscript.sh
    - Within each of the slave directory, you can find a file called
      _master_dir, this file contains the master's working directory.  This is
      useful if some scripts running on a slave need to know where the master
      job is located.  (I use this to aid the transfer of updated .incon files
      across all slaves.)  You can use a command like this to get it back into
      a bash variable:
          MASTERDIR=`cat _master_dir`
          cp ${MASTERDIR}/a ./b
    - I use rsync to copy everything in a dir to another.  This is useful when
      you want to make some changes to a set of PEST setup/files.  Be careful
      with the slashes here.  eg.
          rsync -ar --progress case_1/ case_wai_2

NeSI related:
    - Read the first page when ssh into nesi login node.
    - use command show_my_projects to see what projects you are on, these
      proejcts directory should be where you keep model files etc.
    - compiling must be done on the build nodes, go to build node by ssh
      build-wm.
    - use private keys to simplify the login/scp procedure, on Windows I use
      Putty and related tools such as WinSCP etc.


TODOs
-----
    - make cleaning up easier

"""

# python 2.6 does not support the new/easier subprocess.check_output
def check_output_old(cmd):
    ''' so use os.system with "> /dev/null 2>&1" '''
    import tempfile
    handle, fname = tempfile.mkstemp(prefix='tmpout', dir='.', text=True)
    code = os.system(cmd + "> " + fname)
    with open(fname, 'r') as f:
        out = f.readlines()
    os.close(handle)
    os.remove(fname)
    if code != 0:
        print("Command %s failed: %s" % (cmd, "".join(out)))
    return "".join(out)

def check_output(cmd):
    return subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode()

def write_to(filename, line):
    with open(filename, 'w') as f:
        f.write(line)

def get_master_dir():
    """ _master_dir is created and copied to slave dirs """
    try:
        with open('_master_dir', 'r') as f:
            line = f.readlines()[0].strip()
            return line
    except:
        return '..'

def get_slave_id():
    """ returns a string as id, needs to be called from within a 'slave' directory.
    NOTE _procid should be written by the master program that invokes slaves.
         Otherwise the current (sub) directory name will be used. """
    try:
        with open('_procid', 'r') as f:
            line = f.readlines()[0].strip()
            return line
    except:
        # get get only the last part of current working dir
        return os.path.basename(os.path.normpath(os.getcwd()))

def get_master_out():
    try:
        with open('_master_out', 'r') as f:
            line = f.readlines()[0].strip()
            return line
    except:
        return 'STDOUT'

def create_job_name():
    """ use directory's name, and make sure spaces replaced by _, for now. """
    name = os.path.split(check_output("pwd"))[-1].replace(' ','').replace('_','')
    if name.startswith('case'):
        name = 'c' + name[4:]
    return name.strip()

def gen_master_sl(fname="_master_job.sl"):
    jobname = create_job_name()
    txt = [
        "#!/bin/bash",
        "#SBATCH -J %s" % jobname,
        "#SBATCH -A %s         # Project Account" % PROJECT,
        "#SBATCH --time=%s     # Walltime" % WALLTIME_MASTER,
        # "#SBATCH --ntasks=1          # number of tasks",
        # "#SBATCH --mem=%s  # memory/cpu (in MB)" % MEM_MASTER,
        # # "#SBATCH --workdir=%s  # working dir" % MAIN_DIR,
        # "#SBATCH --ntasks=%i         # number of tasks" % int(NUM_SLAVES / 5),
        "#SBATCH --ntasks=1          # number of tasks",
        "#SBATCH --cpus-per-task=%i  # number of CPUs" % max(int(NUM_SLAVES / 5),1),
        "#SBATCH --overcommit        # allow many tasks on one CPU",
        "#SBATCH --mem=%i  # memory/cpu (in MB)" % (int(MEM_PER_SLAVE) * int(NUM_SLAVES / 5) + int(MEM_MASTER)),
        "#SBATCH --profile task",
        "#SBATCH --acctg-freq=1",
        ]
    if use_input:
        txt += ["#SBATCH --input=_input"]
    txt += [
        "",
        "echo running %s..." % fname,
        "",
        "rm -rf _jobs",
        "mkdir _jobs",
        "",
        "function finish {",
        "  cd _jobs",
        "  for f in *",
        "  do",
        "    echo EXIT $SLURM_JOB_ID, master script cancelling child job: $f",
        "    scancel --clusters=maui,mahuika $f",
        "  done",
        "  cd ..",
        "}",
        "trap finish EXIT",
        "",
        ]
    txt += ENV_MODULES
    txt += [
        "",
        "MASTERDIR=`pwd`",
        "echo ${MASTERDIR} > _master_dir",
        "",
        # "rm -f run_ns_pr.log",
        # "echo ${MASTERDIR}/run_ns_pr.log > _logfile",
        "",
        "# run master",
        # "srun --exclusive -n1 bash %s/_run_master.sh" % MAIN_DIR,
        "bash %s/_run_master.sh &" % MAIN_DIR,
        "",
        "",
        "# run slaves",
        "echo starting %i PEST slaves on single node..." % NUM_SLAVES,
        "for i in {1..%i}" % NUM_SLAVES,
        "do",
        "    bash _run_a_slave.sh ${i} &",
        "done",
        "",
        "# for both background shell jobs (master and slaves srun) to finish",
        "wait",
        "",
        ]
    with open(fname, 'w') as f:
        f.write("\n".join(txt))

def gen_slaves_sl(fname="_slaves_job.sl"):
    # be careful, might not work, if str contains txt such as 'MB'
    jobname = 'S_' + create_job_name()
    txt = "\n".join([
        "#!/bin/bash",
        "#SBATCH -J %s" % jobname,
        "#SBATCH -A %s         # Project Account" % PROJECT,
        "#SBATCH --time=%s     # Walltime" % WALLTIME_SLAVES,
        "#SBATCH --ntasks=1          # number of tasks",
        "#SBATCH --cpus-per-task=%i  # number of CPUs" % max(int(NUM_SLAVES / 10),1),
        "#SBATCH --overcommit        # allow many tasks on one CPU",
        "#SBATCH --mem=%i  # memory/cpu (in MB)" % (int(MEM_PER_SLAVE) * int(NUM_SLAVES / 5)),
        "#SBATCH --profile task",
        "#SBATCH --acctg-freq=1",
        # "#SBATCH --workdir=%s  # working dir" % MAIN_DIR,
        "echo running %s..." % fname,
        ] + ENV_MODULES + [
        "",
        "# run slaves",
        "echo starting %i PEST slaves on single node..." % NUM_SLAVES,
        "for i in {1..%i}" % NUM_SLAVES,
        "do",
        # "    echo slave id ${i}",
        "    bash _run_a_slave.sh ${i} &",
        "done",
        "",
        "# for both background shell jobs (master and slaves srun) to finish",
        "wait",
        "",
        ])
    f = open(fname, 'w')
    f.write(txt)
    f.close()

def gen_forward_sl(cmd, fname="_forward.sl"):
    cwd = os.getcwd()
    txt = "\n".join([
        "#!/bin/bash",
        "#SBATCH -J %s" % get_slave_id(),
        "#SBATCH -A %s    # Project Account" % PROJECT,
        "#SBATCH --time=%s    # Walltime" % WALLTIME_FORWARD,
        "#SBATCH --ntasks=1    # number of tasks",
        "#SBATCH --mem=%s    # memory/cpu (in MB)" % MEM_FORWARD,
        # "#SBATCH --workdir=%s    # working dir" % cwd,
        # "#SBATCH --output=%s # print to master .out" % get_master_out(),
        # "#SBATCH --error=%s # print to master .out" % get_master_out(),
        # "#SBATCH --open-mode=append # make sure don't overwrite master out",
        "",
        "function finish {",
        "  echo -- forward job $SLURM_JOB_ID exiting at $(pwd)",
        "  rm _status_on_nesi",
        "  rm %s/_jobs/$SLURM_JOB_ID" % get_master_dir(),
        "}",
        "trap finish EXIT",
        "",
        "",
        "echo -- forward job $SLURM_JOB_ID starting at $(pwd)",
        "touch %s/_jobs/$SLURM_JOB_ID" % get_master_dir(),
        "",
        ] + ENV_MODULES + [
        "",
        "srun %s" % cmd,
        "",
        ])
    with open(fname, 'w') as f:
        f.write(txt)

def gen_forward_mahuika_sl(cmd, fname="_forward.sl"):
    cwd = os.getcwd()
    txt = "\n".join([
        "#!/bin/bash -e",
        "#SBATCH -J %s" % get_slave_id(),
        "#SBATCH -A %s    # Project Account" % PROJECT_MAHUIKA,
        "#SBATCH --export=NONE      # don't carry env over",
        "#SBATCH --time=%s    # Walltime" % WALLTIME_FORWARD,
        "#SBATCH --ntasks=%i    # number of tasks" % MAHUIKA_NTASKS,
        "#SBATCH --mem=%s    # memory/cpu (in MB)" % MEM_FORWARD,
        #"#SBATCH --mem-per-cpu=%i  # memory/cpu (in MB)" % int(float(MEM_FORWARD)/float(MAHUIKA_NTASKS)),
        #"#SBATCH --mem=%s    # memory/cpu (in MB)" % MEM_FORWARD,
        #"#SBATCH --output=%s # print to master .out" % get_master_out(),
        #"#SBATCH --error=%s # print to master .out" % get_master_out(),
        #"#SBATCH --open-mode=append # make sure don't overwrite master out",
        "",
        "function finish {",
        "  echo -- forward job $SLURM_JOB_ID exiting at $(pwd)",
        "  rm _status_on_nesi",
        "  rm %s/_jobs/$SLURM_JOB_ID" % get_master_dir(),
        "}",
        "trap finish EXIT",
        "",
        "",
        "echo -- forward job $SLURM_JOB_ID starting at $(pwd)",
        "touch %s/_jobs/$SLURM_JOB_ID" % get_master_dir(),
        "",
        ] + ENV_MODULES_MAHUIKA + [
        "",
        "export SLURM_EXPORT_ENV=ALL",
        "srun %s" % cmd,
        "",
        ])
    with open(fname, 'w') as f:
        f.write(txt)


def gen_forward_maui_sl(cmd, fname="_forward.sl"):
    cwd = os.getcwd()
    txt = "\n".join([
        "#!/bin/bash -e",
        "#SBATCH -J %s" % get_slave_id(),
        "#SBATCH -A %s    # Project Account" % PROJECT_MAUI,
        "#SBATCH --clusters=maui    # from mahuika to maui",
        "#SBATCH --export=NONE      # don't carry env over",
        "#SBATCH --time=%s    # Walltime" % WALLTIME_FORWARD,
        "#SBATCH --ntasks=%i    # number of tasks" % MAUI_NTASKS,
        #"#SBATCH --mem-per-cpu=%i  # memory/cpu (in MB)" % int(float(MEM_FORWARD)/float(MAUI_NTASKS)),
        "#SBATCH --mem=%s    # memory/cpu (in MB)" % MEM_FORWARD,
        #"#SBATCH --output=%s # print to master .out" % get_master_out(),
        #"#SBATCH --error=%s # print to master .out" % get_master_out(),
        #"#SBATCH --open-mode=append # make sure don't overwrite master out",
        "#SBATCH --partition=nesi_research",
        #"#SBATCH --qos=nesi_debug",
        "",
        "function finish {",
        "  echo -- forward job $SLURM_JOB_ID exiting at $(pwd)",
        "  rm _status_on_nesi",
        "  rm %s/_jobs/$SLURM_JOB_ID" % get_master_dir(),
        "}",
        "trap finish EXIT",
        "",
        "",
        "echo -- forward job $SLURM_JOB_ID starting at $(pwd)",
        "touch %s/_jobs/$SLURM_JOB_ID" % get_master_dir(),
        "",
        ] + ENV_MODULES_MAUI + [
        "",
        "export SLURM_EXPORT_ENV=ALL",
        "srun %s" % cmd,
        "",
        ])
    with open(fname, 'w') as f:
        f.write(txt)

def gen_run_master(fname="_run_master.sh"):
    if use_input:
        cmd = "%s %s %s /h :%s < _input" % (BEOPEST, PST_NAME, SWITCHES, PORT)
    else:
        cmd = "%s %s %s /h :%s" % (BEOPEST, PST_NAME, SWITCHES, PORT)
    txt = "\n".join([
        "#!/bin/bash",
        "",
        "echo Master working at $(hostname)",
        "echo $(hostname) > _master_host",
        "",
        "echo $(pwd)/slurm-${SLURM_JOB_ID}.out > _master_out",
        "",
        "echo Master running command: %s" % cmd,
        cmd,
        "",
        ])
    f = open(fname, 'w')
    f.write(txt)
    f.close()

def gen_run_single_slave(fname="_run_a_slave.sh"):
    # use jobid and procid to ensure slave directories are unique.
    # add ./ into PATH so that PEST can run model files without ./
    # "slave_${SLURM_JOB_ID}_${SLURM_STEP_ID}_${SLURM_PROCID}_${SLURM_LOCALID}_$1"
    slave_name = "slave_${SLURM_JOB_ID}_$1"
    slave_dir = os.path.join(SLAVEDIR, slave_name)
    cmd = "%s %s /h ${MASTERHOST}:%s" % (BEOPEST, PST_NAME, PORT)
    lines = [
        "#!/bin/bash",
        "",
        "echo running %s $1 in %s..." % (fname, slave_dir),
        "",
        "sleep 5",
        "mkdir -pv %s" % slave_dir,
        # "cp * %s/" % slave_dir,
        "cp %s %s/" % (FILE_LIST, slave_dir),
        "cd %s" % slave_dir,
        "echo A slave working at $(hostname):%s" % slave_dir,
        "echo %s > _master_dir" % MAIN_DIR, # needed for model scripts to copy incon/save
        "echo ${SLURM_JOB_ID}_$1 > _procid", # needed for obsreref book keeping
        "MASTERHOST=`awk '{print $1}' %s/_master_host`" % MAIN_DIR,
        "export PATH=./:$PATH",
        "echo Slave $(hostname)_${1} running command: %s" % cmd,
        # "sysctl fs.file-nr",
        # "chmod a+x model.bat",
        # "chmod a+x r_model.bat",
        # "chmod a+x d_model.bat",
        cmd,
        "",]
    if SUMMARY_LARGE_FILES:
        lines += [
            "# head and tail big result files",
            "for f in %s" % SUMMARY_LARGE_FILES,
            "do",
            "  head --lines=20 $f > $f.head",
            "  tail --lines=20 $f > $f.tail",
            "  echo Removing $f...",
            "  rm $f",
            "done",
            "",]
    if KEEP_TARGZ_SLAVES:
        # lines += [
        #     "cd ..",
        #     "",]
        lines += [
            "tar -zcf %s/%s.tar.gz %s" % (MAIN_DIR, slave_name, slave_dir),
            "",]
    with open(fname, 'w') as f:
        f.write("\n".join(lines))

def gen_test_dir(fname="_copy_to_test.sh"):
    # make a test directory, used for manually checking slave directory
    slave_dir = "%s/test" % MAIN_DIR
    txt = "\n".join([
        "#!/bin/bash",
        "",
        "mkdir -pv %s" % slave_dir,
        "cp %s %s/" % (FILE_LIST, slave_dir),
        ])
    f = open(fname, 'w')
    f.write(txt)
    f.close()


def sbatch_check(cmd, retry_sec=None, retry_limit=10):
    """ this runs sbatch and detects errors, only return slurm job id if
    successful.  If retry is not None, sbatch will be called again after
    sleeping retry seconds, with a limit number of tries.
    """
    import sys
    if retry_sec is None:
        retry_limit = 0
    i = 0
    jobid = None
    while i < (retry_limit + 1):
        print("running %s ..." % cmd)
        out = check_output(cmd)
        i += 1
        try:
            jobid = out.strip().split()[3]
            break
        except IndexError:
            print("sbatch error, try no. %i: %s" % (i, out.strip()))
        except:
            print("sbatch unexpected error:", sys.exc_info()[0])
            raise
        #if 'error' in out:
        #    print("%i: %s" % (i, out.strip()))
        #else:
        #    jobid = out.strip().split()[3]
        #    break
    return jobid

def proc_args():
    # couldn't use argparse because NeSI Python still default to 2.6
    import sys
    def get_opt(o):
        for i,s in enumerate(sys.argv[1:]):
            if s == o:
                return sys.argv[1:][i+1]
    def usage():
        print('\n'.join([
            "This script submits BeoPEST/PEST_HP job on NeSI.",
            "  -f, --forward COMMAND",
            "      Submit single forward run, COMMAND must be supplied.",
            "      Optional, if not supplied the whole PEST master/slaves run",
            "      will be submitted instead",
            "  -f2, --forward2 COMMAND",
            "      This is the same as -f/--forward.  But instead using the",
            "      less reliable 'sbatch --wait', now it uses 'swait'.",
            "  -f3, --forward3 COMMAND",
            "      This is the same as -f/--forward.  But file locking",
            "      mechanism instead of swait/sbatch that replies on good",
            "      communication",
            "  -f3mahuika, --forward3mahuika COMMAND",
            "      This is the same as -f3/--forward3, but submit to Mahuika",
            "      instead.",
            "  -f3maui, --forward3maui COMMAND",
            "      This is the same as -f3/--forward3, but submit to Maui",
            "      instead.",
            "  -f3x, --forward3x COMMAND",
            "      This is the same as -f3/--forward3, but submission to",
            "      Maui or Mahuika depends on settings in goPESTconfig.toml",
            "  --dirs DIR_PATTERNi --jobnowait COMMAND",
            "      Used to submit many jobs of COMMAND in directories specified",
            "      by DIR_PATTERN",
            "  --cancel",
            "      Cancel ALL jobs originated from current directory (_jobs).",
            ]))
    option = {
        "forward": None,
        "forward2": None,
        "forward3": None,
        "forward3mahuika": None,
        "forward3maui": None,
        "forward3x": None,
        "dirs": None,
        "jobnowait": None,
        "cancel": False,
    }
    if '--help' in sys.argv[1:]:
        usage()
    elif '-h' in sys.argv[1:]:
        usage()
    elif '--forward' in sys.argv[1:]:
        option['forward'] = get_opt('--forward')
    elif '-f' in sys.argv[1:]:
        option['forward'] = get_opt('-f')
    elif '--forward2' in sys.argv[1:]:
        option['forward2'] = get_opt('--forward2')
    elif '-f2' in sys.argv[1:]:
        option['forward2'] = get_opt('-f2')
    elif '--forward3' in sys.argv[1:]:
        option['forward3'] = get_opt('--forward3')
    elif '-f3' in sys.argv[1:]:
        option['forward3'] = get_opt('-f3')
    elif '--forward3mahuika' in sys.argv[1:]:
        option['forward3mahuika'] = get_opt('--forward3mahuika')
    elif '-f3mahuika' in sys.argv[1:]:
        option['forward3mahuika'] = get_opt('-f3mahuika')

    elif '--forward3maui' in sys.argv[1:]:
        option['forward3maui'] = get_opt('--forward3maui')
    elif '-f3maui' in sys.argv[1:]:
        option['forward3maui'] = get_opt('-f3maui')
    elif '--forward3x' in sys.argv[1:]:
        option['forward3x'] = get_opt('--forward3x')
    elif '-f3x' in sys.argv[1:]:
        option['forward3x'] = get_opt('-f3x')
    elif '--dirs' in sys.argv[1:]:
        option['dirs'] = get_opt('--dirs')
        option['jobnowait'] = get_opt('--jobnowait')
    elif '--cancel' in sys.argv[1:]:
        option['cancel'] = True
    return option

def submit_cli(argv=[]):
    if cfg['mode'] != 'nesi':
        raise Exception('Error! gopest submit can only run with mode = "nesi" ')

    from time import sleep
    # You can use chain jobs to create dependencies between jobs.
    # SLURM has an option -d or "--dependency" that allows to
    # specify that a job is only allowed to start if another job finished.
    #
    # use 'after:' instead of 'afterok:' to start slaves after master STARTED
    # (not after it's done)

    SCRIPT_DIR = os.getcwd()
    option = proc_args()

    ### print basic info
    print("You are working under directory: %s" % SCRIPT_DIR)
    write_to('_pest_dir', PESTDIR)
    write_to('_tough2', SIMULATOR)
    write_to('_master_dir', SCRIPT_DIR)

    # for job management, keeps a list of jobs submitted from this directory
    if not os.path.exists('_jobs'):
        os.makedirs('_jobs')

    ### if forward only submit single run job
    if option['forward'] is not None:
        gen_forward_sl(option['forward'])
        # important to have --wait here to block until job finish
        jobid = sbatch_check("sbatch --wait _forward.sl", retry_sec=30)
        if jobid is not None:
            ttime = check_output("sacct -j %s.0 -o totalcpu -n" % jobid).strip()
            print("\nForward job %s finished after %s" % (jobid, ttime))
        else:
            print("\nFailed to submit _forward.sl")
        exit()
    elif option['forward2'] is not None:
        """ The is the same as -f/--forward, but use the more reliable swait.

        It happened a few times that sbatch --wait returned early with error:
        sbatch: error: slurm_receive_msg: Socket timed out on send/recv
        operation. This may be triggered when slurm daemon is acutely busy.  The
        actual job in this case can still be running.  So Gene (from NeSI)
        suggested using swait script.
        """
        gen_forward_sl(option['forward2'])
        jobid = check_output("sbatch _forward.sl").strip().split()[3]
        print("\nJob %s submitted." % jobid)
        print("/share/bin/swait %s" % jobid)
        os.system("/share/bin/swait %s" % jobid)
        ttime = check_output("sacct -j %s.0 -o totalcpu -n" % jobid).strip()
        print("\nForward job %s finished after %s" % (jobid, ttime))
        exit()
    elif option['forward3'] is not None:
        """ The is the same as -f/--forward, but use lock files instead of
        swait or sbatch --wait, which replies on NeSI's communications.
        """
        gen_forward_sl(option['forward3'])
        # _status_on_nesi will be removed once the _forward.sl finish
        # regardless how it terminated.
        with open('_status_on_nesi', 'w') as f:
            pass
        import random
        wait_t = random.random() # * 20.0 * 60.0
        print('.. waiting %f sec before submit ..' % wait_t)
        sleep(wait_t)
        jobid = sbatch_check("sbatch _forward.sl", retry_sec=30, retry_limit=50)
        if jobid is not None:
            while os.path.isfile('_status_on_nesi'):
                sleep(120)
            ttime = check_output("sacct -j %s.0 -o totalcpu -n" % jobid).strip()
            print("\nForward job %s finished after %s" % (jobid, ttime))
        else:
            os.remove('_status_on_nesi')
            print("\nFailed to submit _forward.sl")
        exit()
    elif option['forward3x'] is not None:
        """ The is the same as -f/--forward, but use lock files instead of
        swait or sbatch --wait, which replies on NeSI's communications.
        """
        if cfg['nesi']['cluster_forward'] == 'mahuika':
            cmd = cfg['nesi']['mahuika']['executable'] + ' ' + option['forward3x']
            print('submit_beopest.py runs command (mahuika)' + cmd)
            gen_forward_mahuika_sl(cmd)
        elif cfg['nesi']['cluster_forward'] == 'maui':
            cmd = cfg['nesi']['maui']['executable'] + ' ' + option['forward3x']
            print('submit_beopest.py runs command (maui)' + cmd)
            gen_forward_maui_sl(cmd)
        else:
            raise Exception('only supports mahuika or maui')
        # _status_on_nesi will be removed once the _forward.sl finish
        # regardless how it terminated.
        with open('_status_on_nesi', 'w') as f:
            pass
        import random
        wait_t = random.random() * 5.0 # * 20.0 * 60.0
        print('.. waiting %f sec before submit ..' % wait_t)
        sleep(wait_t)
        jobid = sbatch_check("sbatch _forward.sl", retry_sec=30, retry_limit=50)
        if jobid is not None:
            while os.path.isfile('_status_on_nesi'):
                sleep(30)
            ttime = check_output("sacct --clusters=mahuika -j %s.0 -o totalcpu -n" % jobid).strip()
            print("\nForward job %s finished after %s" % (jobid, ttime))
        else:
            os.remove('_status_on_nesi')
            print("\nFailed to submit _forward.sl")
        exit()
    elif option['forward3mahuika'] is not None:
        """ The is the same as -f/--forward, but use lock files instead of
        swait or sbatch --wait, which replies on NeSI's communications.
        """
        gen_forward_mahuika_sl(option['forward3mahuika'])
        # _status_on_nesi will be removed once the _forward.sl finish
        # regardless how it terminated.
        with open('_status_on_nesi', 'w') as f:
            pass
        import random
        wait_t = random.random() # * 20.0 * 60.0
        print('.. waiting %f sec before submit ..' % wait_t)
        sleep(wait_t)
        jobid = sbatch_check("sbatch _forward.sl", retry_sec=30, retry_limit=50)
        if jobid is not None:
            while os.path.isfile('_status_on_nesi'):
                sleep(120)
            ttime = check_output("sacct --clusters=mahuika -j %s.0 -o totalcpu -n" % jobid).strip()
            print("\nForward job %s finished after %s" % (jobid, ttime))
        else:
            os.remove('_status_on_nesi')
            print("\nFailed to submit _forward.sl")
        exit()
    elif option['forward3maui'] is not None:
        """ The is the same as -f/--forward, but use lock files instead of
        swait or sbatch --wait, which replies on NeSI's communications.
        """
        gen_forward_maui_sl(option['forward3maui'])
        # _status_on_nesi will be removed once the _forward.sl finish
        # regardless how it terminated.
        with open('_status_on_nesi', 'w') as f:
            pass
        import random
        wait_t = random.random() # * 20.0 * 60.0
        print('.. waiting %f sec before submit ..' % wait_t)
        sleep(wait_t)
        jobid = sbatch_check("sbatch _forward.sl", retry_sec=30, retry_limit=50)
        if jobid is not None:
            while os.path.isfile('_status_on_nesi'):
                sleep(120)
            ttime = check_output("sacct --clusters=maui -j %s.0 -o totalcpu -n" % jobid).strip()
            print("\nForward job %s finished after %s" % (jobid, ttime))
        else:
            os.remove('_status_on_nesi')
            print("\nFailed to submit _forward.sl")
        exit()
    elif option['dirs'] is not None and option['jobnowait'] is not None:
        import glob
        import shutil
        write_to('_submit.out', '\n'.join([
            'Running --dirs "%s" --jobnowait "%s"' % (option['dirs'], option['jobnowait']),
            '',
            ]))
        for d in glob.glob(option['dirs']):
            shutil.copy('_master_dir', d)
            shutil.copy('_tough2', d)
            cwd = os.getcwd()
            os.chdir(d)
            write_to('_master_out', cwd+'/_submit.out')
            gen_forward_sl(option['jobnowait'])
            import random
            wait_t = random.random() * 20.0 * 60.0
            print('.. waiting %f sec before submit ..' % wait_t)
            sleep(wait_t)
            jobid = sbatch_check("sbatch _forward.sl", retry_sec=30, retry_limit=50)
            os.chdir(cwd)
        exit()
    elif option['cancel'] is True:
        import glob
        for f in glob.glob('_jobs/*'):
            print('Cancelling %s' % os.path.basename(f))
            os.system('scancel --clusters=maui,mahuika %s' % os.path.basename(f))
        exit()
                

    ### generate slurm scripts etc.
    gen_master_sl()
    gen_slaves_sl()
    gen_run_master()
    gen_run_single_slave()
    gen_test_dir()

    # slave files and dir will be handled within _run_a_slave.sh

    ### submit beopest master job, and get job id, master.sl will record hostname
    out = check_output("sbatch _master_job.sl").strip()
    print("BeoPEST/PEST_HP Master and Slaves: ", out)
    dependency = out.split()[3]

    write_to('_master_slurm_id', dependency)

    ### submit beopest slaves job, depend on run after master started
    cmd = "sbatch --dependency after:%s _slaves_job.sl" % dependency
    #out = check_output(cmd).strip()
    #print("BeoPEST Slaves: ", out)
    print("Add more slaves (after master job is submitted) by using command:")
    print("    %s" % cmd)


if __name__ == "__main__":
    submit_cli()
