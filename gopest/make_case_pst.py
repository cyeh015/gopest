from gopest.par import generate_params_and_tpl
from gopest.obs import generate_obses_and_ins

from gopest.common import config
from gopest.common import runtime

import os
import re
import shutil

def replace_section(begin_sec, end_sec, pcf_text, repl):
    """ returns PEST control file (passed in as a multiline string) with section
    between begin_sec and end_sec replaced by string repl.  It does not matter
    if repl has line breaks at the end or start, they will be cleaned up so the
    final file has no empty lines. """
    pattern = re.compile(r'\n *%s *\n.*?\n *%s *\n' % (re.escape(begin_sec), re.escape(end_sec)), flags=re.DOTALL)
    repl = '\n%s\n%s\n%s\n' % (begin_sec, repl.strip("\n"), end_sec)
    result, cnt = pattern.subn(repl, pcf_text)
    if cnt < 1:
        raise Exception("unable to find loaction between section %s and %s" % (begin_sec, end_sec))
    return result

def get_lines(filename):
    """ return all non-empty lines froma file as a single string, with a line
    count. """
    f = open(filename, 'rU')
    lines, cnt = '', 0
    for line in f:
        if line.strip():
            cnt += 1
            lines += line
    f.close()
    return lines, cnt

def replace_nth_line(longstring, i, repl):
    """ replace ith line with repl, if repl is a function, it will be called to
    process the original line. """
    line_i = re.compile(r'([^\n]*\n){%i}' % i, flags=re.MULTILINE)
    m = line_i.match(longstring)

    if m:
        if isinstance(repl, str):
            real_repl = repl
        elif hasattr(repl, '__call__'):
            real_repl = repl(m.group(1))
        else:
            # if not a string or callable, try convert it into string
            real_repl = str(repl)
        return longstring[:m.start(1)] + real_repl.strip() + '\n' + longstring[m.end(1):]
    else:
        raise Exception("replace_nth_line() failed to replace line number %i" % i)

#############################################################################

def fixpcf_modelcmd(fpst):
    """ update PEST case file (.pst) with model command line and distribution
    files
    """
    fsave = runtime['filename']['save']
    fincon = runtime['filename']['incon']
    fdatns = runtime['filename']['dat_seq'][0]
    flstpr = runtime['filename']['lst_seq'][-1]

    fpst_bk = fpst + '.backup'
    if not os.path.isfile(fpst):
        print('Error: %s does not exist.' % fpst)
        exit(1)
    if os.path.isfile(fpst_bk):
        os.remove(fpst_bk)
    os.rename(fpst, fpst_bk)

    try:
        with open(fpst_bk,'r') as fin:
            pcf_text = fin.read()

        model_cmd = 'gopest run-pest-model\n'
        model_inout = "\n".join([
            'pest_model.tpl pest_model.dat',
            'pest_model.ins  pest_model.obf',
        ])
        filedist = "\n".join([
            '2 %s %s %s %s' % (fsave, fincon, fincon, fincon),
            '1 %s %s.999' % (fsave, fincon),
            '1 %s %s.999' % (fdatns, fdatns),
            '1 %s %s.999' % (flstpr, flstpr),
            '1 pest_model.dat pest_model.dat.999',
            'command = "gopest save-iter-model"',
        ])

        pcf_text = replace_section("* model command line", "* model input/output",
            pcf_text, model_cmd)
        pcf_text = replace_section("* model input/output", "* prior information",
            pcf_text, model_inout)
        pcf_text = replace_section("* distribution files", "# end",
            pcf_text, filedist)

        with open(fpst, 'w') as fout:
            fout.write(pcf_text)
        print('+++ PEST case control file edited, original file saved as %s' % fpst_bk)
    except Exception as e:
        print(e)
        print('update_case_pst.py unable to proceed, restoring.')
        os.rename(fpst_bk, fpst)

def fixpcf_parobs(fpst, dopar=True, doobs=True):
    """ update PEST case file (.pst) with parameter and observation data
    """
    if dopar is False and doobs is False:
        return

    fpst_bk = fpst + '.backup'
    if not os.path.isfile(fpst):
        print('Error: %s does not exist.' % fpst)
        exit(1)
    if os.path.isfile(fpst_bk):
        os.remove(fpst_bk)
    os.rename(fpst, fpst_bk)

    try:
        with open(fpst_bk,'r') as fin:
            pcf_text = fin.read()

        if dopar:
            par_data, n_par = get_lines('.pest_par_data')
            pcf_text = replace_section("* parameter data", "* observation groups",
                pcf_text, par_data)
            print('+++ found %i parameters' % n_par)

            # replace the count of parameters
            def replace_par_cnts(orig):
                """ first two number is n_par and n_obs """
                nums = orig.split()
                return ' '.join([str(n_par)] + nums[1:])
            pcf_text = replace_nth_line(pcf_text, 4, replace_par_cnts)

        if doobs:
            obs_data, n_obs = get_lines('.pest_obs_data')
            pcf_text = replace_section("* observation data", "* model command line",
                pcf_text, obs_data)
            print('+++ found %i observations' % n_obs)

            # replace the count of parameters
            def replace_obs_cnts(orig):
                """ first two number is n_par and n_obs """
                nums = orig.split()
                return ' '.join(nums[:1] + [str(n_obs)] + nums[2:])
            pcf_text = replace_nth_line(pcf_text, 4, replace_obs_cnts)

        with open(fpst, 'w') as fout:
            fout.write(pcf_text)
        print('+++ PEST case control file edited, original file saved as %s' % fpst_bk)
    except Exception as e:
        print(e)
        print('update_case_pst.py unable to proceed, restoring.')
        os.rename(fpst_bk, fpst)

def copy_model_files():
    """ user specifies model's original files in [model.original]section
    These files will be copied to the working directory, with goPEST's internal
    naming convention.
    """
    def copy_to_cwd(filename, newbase):
        """ copy to working dir and rename, but keeping all extention (to lower case) """
        newname = newbase + os.path.splitext(filename)[1].lower()
        print("  copy '%s' -> '%s'" % (filename, newname))
        shutil.copy2(filename, newname)

    for f in config['model']['original']['geometry-files']:
        copy_to_cwd(f, './g_real_model')
    copy_to_cwd(config['model']['original']['incon-file'], './real_model_incon')

    # copy input and output files for the sequence of 'ns', 'pr', etc
    sequence = config['model']['sequence']
    for seq in sequence:
        copy_to_cwd(config['model']['original']['%s-input-file' % seq], './real_model_%s' % seq)
        if '%s-output-file' % seq in config['model']['original']:
            copy_to_cwd(config['model']['original']['%s-output-file' % seq], './real_model_%s' % seq)
    # make a copy of first dat to keep as original (handy for goPESTpar etc)
    copy_to_cwd(config['model']['original']['%s-input-file' % sequence[0]], './real_model_original')

def make_case_cli(argv=[]):
    """ runs goPEST to set up par and obs entries """
    for a in argv[1:]:
        if a not in ['--no-copy', '--no-par', '--no-obs']:
            raise Exception('Unrecognised option "%s".' % a)
    if '--no-copy' in argv:
        print('+++ use existing model files')
    else:
        print('+++ copy from original model files')
        copy_model_files()

    fgeo = runtime['filename']['geom']
    fdato = runtime['filename']['dat_orig']
    fdats = runtime['filename']['dat_seq']

    dopar = False
    if '--no-par' not in argv:
        print('+++ running goPEST to get par')
        print('  gopestpar', fdato, 'pest_model.tpl', '.pest_par_data')
        generate_params_and_tpl(fdato, 'pest_model.tpl', '.pest_par_data')
        dopar = True

    doobs = False
    if '--no-obs' not in argv:
        print('+++ running goPEST to get obs')
        print('  gopestobs', fgeo, fdats[-1], 'pest_model.ins', '.pest_obs_data')
        generate_obses_and_ins(fgeo, fdats[-1], 'pest_model.ins', '.pest_obs_data')
        doobs = True

    # unfortunately I need to use 'real_model_original_pr.dat' here because it
    # has many GENERs that may not exist in natural state, while still being
    # needed in observations, eg. Production gener's block, hopefully this is
    # okay because we usually don't need to get any actual values out of the
    # real_model_original_pr.dat model.

    # edit them into PEST case control file
    fpst = config['pest']['case-name'] + '.pst'
    fixpcf_parobs(fpst, dopar=dopar, doobs=doobs)
    fixpcf_modelcmd(fpst)




