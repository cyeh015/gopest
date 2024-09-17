default_cfg = """# This is goPEST's main configuration file.

[pest]
dir = ""
executable = "pest_hp"
port = "24001"
num_slaves = 2
slave_dirs = ""

case-name = 'case'
switches = []
# additional swiches for beopest, eg /s for restart, /p1 for parallise 1st model run
# should not use /p1 with svda, no /p1 with obsreref_10 either
# /hpstart, make sure PST_NAME.hp exists
# /i jco reuse, make sure PST_NAME.jco exists
# NOTE it's possible to use /hpstart and /i together, will start update tests right away
# NOTE working directory is assumed to be where this script is launched

[model]
skip = false # skips actual simulation, existing model output is used
skip-pr = false
silent = true
sequence = ['ns', 'pr']

[model.original]
# these original model files will be renamed to goPEST's internal convention,
# which is usually something like real_model_xx, where xx is the sequence name.

# specify at least Mulgrid geometry file here, needs .msh etc if running Waiwera
geometry-files = ['raw/gOH68954.dat', 'raw/gOH68954.msh']
incon-file = 'raw/NaturalState/waiOH68954_NS_486_incon.h5'
ns-input-file = 'raw/NaturalState/waiOH68954_NS_486.json'
pr-input-file = 'raw/Production/waiOH68954_PR_486.json'

# optional original output file, useful for debug
ns-output-file = 'raw/NaturalState/waiOH68954_NS_486.h5'
pr-output-file = 'raw/Production/waiOH68954_PR_486.h5'

[simulator]
input-type = "waiwera" # "waiwera" or "aut2"
output-type = "h5" # "listing" or "h5", will always be "h5" if input-type = "waiwera"

executable = 'waiwera'

# these will be attached to the end of simulation command (useful for waiwera)
cmd-options = []

[nesi]
project = "uoa00123"
cluster_master = "mahuika"
cluster_forward = "maui"
walltime_master = "72:00:00" # hour:min:sec
walltime_forward = "12:00:00" # hour:min:sec
ntasks = 40

[nesi.maui]
project = "uoa00123"
walltime_forward = "12:00:00" # hour:min:sec
ntasks = 40
env_init = [
    "module swap PrgEnv-cray PrgEnv-gnu",
    "module swap gcc gcc/8.3.0",
    "module load cray-python",
    "export HDF5_USE_FILE_LOCKING=FALSE", # avoids h5py unable to lock file (Maui only)
    "export PYTHONPATH=/nesi/project/uoa00124/pytough:/nesi/project/uoa00124/utils:/nesi/project/uoa00124/software/py27-maui/:$PYTHONPATH",
    "printenv PYTHONPATH",
]

[nesi.mahuika]
project = "uoa00123"
walltime_forward = "24:00:00" # hour:min:sec
ntasks = 40
env_init = [
    "module load gimkl/2018b",
]

[files]
# all files required by a PEST slave and forward model run:
slave = [
    "g_real_model.dat",
    "g_real_model.msh",
    "real_model_original.json",
    "real_model.incon.h5",
    # observation data files
    "data.json",
    # these are for forward run
    "gs_production.json",
    "real_model_pr.output.json",
    "real_model_pr.time.json",
]
# additional files required by PEST master
master = []

"""
