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


def check_run_status(spath, ends=False):
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
        results['run'][seq]['exists'] = os.path.exists(flsts[i])
        if input_typ== 'waiwera':
            fyaml = flsts[i].replace('.h5', '.yaml')
            results['run'][seq] = nested_dict_update(results['run'][seq],
                                                     waiwera_ends(fyaml))
        else:
            raise NotImplementedError()

    os.chdir(cwd)
    # print('Restored directory %s' % cwd)
    return results

def get_obj_fn(spath):
    print(spath)
    org_dir = os.getcwd()
    os.chdir(spath)
    with open('model.bat', 'w') as f:
        f.write('python pest_model.py --local --skip-run --waiwera')
    shutil.copy('../case_reg.pst', 'case_reg.pst')
    subprocess.call(['pest', 'case_reg.pst'])
    results = read_rec('case_reg.rec')
    os.chdir(org_dir)
    return results

hlp = '''
Usage: gopest check-slaves [--end-time] [--obj-fn] [--dir path_to_slaves]

The check-slaves command searches through slave directories and obtain/collect
their running status etc.  By default, the pest.slave_dirs property from
goPESTconfig.toml is searched. It is possible to specify a different directory
by using argument "--dir".

Extracted information will be dumped into a JSON file "goPESTslaves.json".  Note
that the command will only update/append results into the JSON file if exists.
It tries not to destroy whatever that is already in the file.

At the very minimum, check-slaves will check if model output files exists.
Argument "--end-time" enables extraction of simulation end time (from output
YAML file if running waiwera as simulator).

Argument "--obj-fn" is more destructive.  Within each slave directory, it will
run PEST (with the NOPTMAX set to 0) once with the internal settings set to skip
actual model runs.  This essentially runs PEST so that observations and
objective function will be extracted from model outputs within the slave
directory.

This command runs locally, and does not utilise any slurm/srun/queue facilities.
'''

def check_slaves_cli(argv=[]):
    if len(argv) <= 1:
        print(hlp)
        exit(0)
    else:
        if '--dir' in argv:
            iarg = argv.index('--dir') + 1
            try:
                spath = argv[iarg]
            except IndexError:
                raise Exception('--dir argument needs to be followed by path_to_slaves')
        else:
            spath = config['pest']['slave_dirs']

    start_time = time.time()
    if not all([os.path.exists(spath), os.path.isdir(spath)]):
        raise Exception('Specified path_to_slaves needs to be a valid directory: %s' % spath)

    task_fn = {
        'slaves_status': check_run_status,
        'slaves_objfn': get_obj_fn,
    }
    task = 'slaves_status'

    slave_paths = sorted([p for p in glob.glob(os.path.join(spath, '*')) if os.path.isdir(p)])
    slave_names = [os.path.basename(sp) for sp in slave_paths]

    ncpu = max(1, cpu_count() - 1)
    pool = Pool(ncpu)
    results = pool.map(task_fn[task], slave_paths)

    fout = 'goPESTslaves.json'
    if os.path.exists(fout):
        with open(fout, 'r') as f:
            data = json.load(f)
    else:
        data = {}
    data = nested_dict_update(data, dict(zip(slave_names, results)))
    with open(fout, 'w') as f:
        json.dump(data, f, indent=4, sort_keys=True)

    print('Finished after %f seconds' % (time.time() - start_time))

if __name__ == '__main__':
    check_slaves_cli(sys.argv)
