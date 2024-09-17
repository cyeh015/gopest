from multiprocessing import Pool, cpu_count
import time
import json
import os
import os.path
import sys
import shutil
import glob
import subprocess
import collections.abc

import yaml
import tomlkit
import xlwt

from gopest.common import config
from gopest.common import runtime

def nested_dict_update(d, u):
    """ update a nested dict object with an update dict
    https://stackoverflow.com/a/3233356/2368167
    """
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = nested_dict_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d

def unix2dos(fname):
    import sys
    with open(fname, 'rb') as infile:
        instr = infile.read()
    outstr = instr.replace( b"\r\n", b"\n" ).replace( b"\r", b"\n" ).replace( b"\n", b"\r\n" )
    if len(outstr) == len(instr):
        return
    with open(fname, 'wb') as outfile:
        outfile.write( outstr )

def fixpcf_noptmax(fpst, noptmax=0):
    """ update PEST case file (.pst) with NOPTMAX, number of optimisation
    iterations
    """
    fpst_bk = fpst + '.backup'
    if not os.path.isfile(fpst):
        print('Error: %s does not exist.' % fpst)
        exit(1)
    if os.path.isfile(fpst_bk):
        os.remove(fpst_bk)
    os.rename(fpst, fpst_bk)

    try:
        with open(fpst_bk,'r') as fin, open(fpst, 'w') as fout:
            linesep = None # use current file's line ending
            isec = 7 # start with 7, so that it will never be 7 again
            for line in fin:
                # detect current file's line ending first
                if linesep is None:
                    if line[-2] == '\r' and line[-1] == '\n':
                        linesep = '\r\n'
                    elif line[-1] == '\n':
                        linesep = '\n'
                # find correct line, replace
                isec += 1
                oline = line
                if line.strip().startswith('*') and 'control data' in line:
                    isec = 0
                if isec == 7:
                    # replace first item in line (NOPTMAX)
                    sps = line.split()
                    oline = ' ' + ' '.join([str(noptmax)] + sps[1:] + [linesep])
                fout.write(oline)
    except Exception as e:
        fin.close()
        fout.close()
        print('fixpcf_noptmax() failed to proceed, restoring...')
        os.remove(fpst)
        os.rename(fpst_bk, fpst)
        raise(e)

def read_rec(rec_file):
    values = {}
    with open(rec_file, 'r') as f:
        reading = False
        for line in f:
            if reading:
                if empty_line:
                    empty_line = False
                    continue
                if not line.strip():
                    continue
                if '----->' in line:
                    break
                sps = line.strip().split('=')
                v = float(sps[-1])
                s = sps[0].strip()
                if s == 'Sum of squared weighted residuals (ie phi)':
                    k = 'phi'
                elif s == 'Optimised measurement objective function':
                    k = 'phi measured'
                elif s == 'Optimised regularisation objective function':
                    k =  'phi regularisation'
                elif '"' in s:
                    k = s.split('"')[1]
                else:
                    k, v = None, None
                if k is not None:
                    values[k] = v
            if line.startswith('Objective function ----->'):
                reading, empty_line = True, True
    return values

class message(object):
    """ A Waiwera log (.yaml) message object """
    def __init__(self, msg):
        self._msg = msg
        self.level, self.source, self.event, self.data = msg


def check_sim_ends(spath):
    """ extract summary of waiwera simulation from yaml log """
    def waiwera_ends(fyaml):
        """ return elapsed time in seconds of waiwera simulation time, None if not
        successful """
        try:
            with open(fyaml) as f:
                data = yaml.load(f, Loader=yaml.CSafeLoader)
                r = {''}
                if data[-3][:3] == ['info', 'timestep', 'end']:
                    time = data[-3][3]['time']
                    size = data[-3][3]['size']
                if data[-1][:3] == ['info', 'simulation', 'destroy']:
                    elapsed = data[-1][3]['elapsed_seconds']
                return {'endtime': time, 'stepsize': size, 'elapsed': elapsed}
        except:
            return {}
    cwd = os.getcwd()
    os.chdir(spath)
    print('Working in %s...' % spath)

    results = {'run': {}}
    sequence = config['model']['sequence']
    input_typ = config['simulator']['input-type']
    flsts = runtime['filename']['lst_seq']
    for i,seq in enumerate(sequence):
        results['run'][seq] = {}
        if input_typ== 'waiwera':
            fyaml = flsts[i].replace('.h5', '.yaml')
            results['run'][seq] = waiwera_ends(fyaml)
        else:
            raise NotImplementedError()

    os.chdir(cwd)
    # print('Restored directory %s' % cwd)
    return results

def check_run_status(spath):
    """ extract summary of waiwera simulation from yaml log """
    cwd = os.getcwd()
    os.chdir(spath)
    print('Working in %s...' % spath)

    results = {'run': {}}
    sequence = config['model']['sequence']
    input_typ = config['simulator']['input-type']
    flsts = runtime['filename']['lst_seq']
    for i,seq in enumerate(sequence):
        results['run'][seq] = {}
        results['run'][seq]['exists'] = os.path.exists(flsts[i])

    os.chdir(cwd)
    # print('Restored directory %s' % cwd)
    return results

def get_obj_fn(spath):
    """ Return PEST calculated objective function values by modifying config and
    PEST case file to run a dummy run.  Then read results from case .rec file.

    This is more destructive, but I have decided to leave those modification
    in place after running the command for a couple of reasons:
    1. (lazy) no need to handle undo the mod if exception is raised
    2. (safe) it's probably safer to leave as modified here, reduce possibility
       for user to wipe out existing model output files, which can be costly to
       run

    Unfortunately I need to modify the config.toml file, because gopest run-
    pest-model is involked by PEST, not this script directly.
    """
    cwd = os.getcwd()
    os.chdir(spath)
    print('Working in %s...' % spath)

    # only works if the final real model output file exists
    flst = runtime['filename']['lst_seq'][-1]
    if not os.path.exists(flst):
        print('Real model output file %s is missing, cannot get obj. fn.' % flst)
        os.chdir(cwd)
        return {}

    # modify config to skip model run
    with open('goPESTconfig.toml', 'r') as f:
        cfg = tomlkit.load(f)
    cfg['model']['skip'] = True
    with open('goPESTconfig.toml', 'w') as f:
        tomlkit.dump(cfg, f)

    # modify NOPTMAX in control data .pst file
    fpst = config['pest']['case-name'] + '.pst'
    fixpcf_noptmax(fpst, 0)

    cmd = [
        os.path.join(config['pest']['dir'], config['pest']['executable']),
        config['pest']['case-name'],
        ]
    print('Running: ', cmd)
    results = {}
    subprocess.call(cmd)
    results['obj-fn'] = read_rec('case_reg.rec')

    os.chdir(cwd)
    # print('Restored directory %s' % cwd)
    return results

def export_xls(data):
    phis, regs, others = [], [], []
    for sln,sl in data.items():
        if 'obj-fn' in sl:
            for n in sorted(sl['obj-fn'].keys()):
                if n.startswith('phi'):
                    phis.append(n)
                elif n.startswith('regul_'):
                    regs.append(n)
                else:
                    others.append(n)
            phis, regs, others = sorted(phis), sorted(regs), sorted(others)
            break
    runcs = []
    for sln,sl in data.items():
        if 'run' in sl:
            for rn,r in sl['run'].items():
                runcs += [rn+'.'+c for c in sorted(r.keys())]
            break
    cols = ['slave'] + phis + others + regs + runcs

    wb = xlwt.Workbook()
    ws = wb.add_sheet('slaves')

    i = 0
    for j,c in enumerate(cols):
        ws.write(i, j, c)

    for sln,sl in data.items():
        if 'obj-fn' in sl:
            i += 1
            j = 0
            ws.write(i, j, sln)
            for p in (phis + others + regs):
                j += 1
                if p in sl['obj-fn']:
                    ws.write(i, j, sl['obj-fn'][p])
            for r in runcs:
                j += 1
                rn,sn = r.split('.')
                if 'run' in sl and rn in sl['run'] and sn in sl['run'][rn]:
                    ws.write(i, j, sl['run'][rn][sn])
    wb.save('goPESTslaves.xls')

def init_slave(cfg, rt):
    """ used in multiprocessing Pool to initialise threads with the the updated
    gopest.common.config and gopest.common.runtime
    """
    print('Updating local thread common.config and common.runtime.')
    global config, runtime
    config = cfg
    runtime = rt

hlp = '''
Usage: gopest check-slaves [--help] [--status] [--end-time] [--obj-fn]
                           [--dir path_to_slaves] [--pest-exe pest_executable]
                           [--export-xls]

The check-slaves command searches through slave directories and obtain/collect
their running status etc.  By default, the pest.slave_dirs property from
goPESTconfig.toml is used. It is possible to specify a different directory by
using argument "--dir".

Extracted information will be dumped into a JSON file "goPESTslaves.json".  Note
that the command will only update/append results into the JSON file if exists.
It tries not to destroy whatever that is already in the file.

"--status" is the fastest option, which only checks if model output files exist
in the lsave directories.  (ie. did the runs produce any output files at all)

"--end-time" enables extraction of simulation end time (from output YAML file if
running waiwera as simulator).

"--obj-fn" is more destructive.  Within each slave directory, it will run PEST
(with the NOPTMAX set to 0) once with the internal settings set to skip actual
model runs.  This essentially runs PEST so that observations and objective
function will be extracted from model outputs within the slave directory.

"--pest-exe" is useful with the "--obj-fn" option when user have the slaves
directories in a different environment than where it was originally run.
pest_executable here can include the path to the executable if it's not already
in the system's PATH.

"--export-xls" is used to export contents of goPESTslaves.json into spreadsheet
file goPESTslaves.xls.  This command can be used alone as it will load existing
goPESTslaves.json.

This command runs locally, and does not utilise any slurm/srun/queue facilities.

This message can be printed with the "--help" argument.  It is possible to
include more than one option at a time.
'''

def check_slaves_cli(argv=[]):
    if '--help' in argv or len(argv) <= 1:
        print(hlp)
        exit(0)
    else:
        # overwrite slave_dirs
        if '--dir' in argv:
            iarg = argv.index('--dir') + 1
            try:
                spath = argv[iarg]
            except IndexError:
                raise Exception('--dir argument needs to be followed by path_to_slaves')
        else:
            spath = config['pest']['slave_dirs']
        # overwrite PEST exe
        if "--pest-exe" in argv:
            iarg = argv.index('--pest-exe') + 1
            try:
                pexe = argv[iarg]
            except IndexError:
                raise Exception('--pest-exe argument needs to be followed by pest_executable')
            # modify the shared module variable
            config['pest']['dir'] = ''
            config['pest']['executable'] = pexe
        else:
            # do nothing, keeps original setting
            pass
        # tasks
        nopts, tasks = 0, []
        if "--status" in argv:
            nopts += 1
            tasks.append('status')
        if "--end-time" in argv:
            nopts += 1
            tasks.append('end-time')
        if "--obj-fn" in argv:
            nopts += 1
            tasks.append('obj-fn')
        xls = False
        if "--export-xls" in argv:
            nopts += 1
            xls = True
        if nopts == 0:
            print(hlp)
            print('Please specify at least one task to perform.')
            exit(0)

    start_time = time.time()
    if not all([os.path.exists(spath), os.path.isdir(spath)]):
        raise Exception('Specified path_to_slaves needs to be a valid directory: %s' % spath)

    task_fn = {
        'end-time': check_sim_ends,
        'status': check_run_status,
        'obj-fn': get_obj_fn,
    }

    slave_paths = sorted([p for p in glob.glob(os.path.join(spath, '*')) if os.path.isdir(p)])
    slave_names = [os.path.basename(sp) for sp in slave_paths]

    ncpu = max(1, cpu_count() - 1)
    print('Starting %i workers to process %i slaves' % (ncpu, len(slave_paths)))
    pool = Pool(ncpu, initializer=init_slave, initargs=(config, runtime))

    fout = 'goPESTslaves.json'
    if os.path.exists(fout):
        with open(fout, 'r') as f:
            data = json.load(f)
    else:
        data = {}

    for task in tasks:
        print('Checking %s...' % task)
        results = pool.map(task_fn[task], slave_paths)
        data = nested_dict_update(data, dict(zip(slave_names, results)))

    with open(fout, 'w') as f:
        json.dump(data, f, indent=4, sort_keys=True)

    if xls:
        export_xls(data)

    print('Finished after %f seconds' % (time.time() - start_time))

if __name__ == '__main__':
    check_slaves_cli(sys.argv)
