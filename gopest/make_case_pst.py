from gopest.par import generate_params_and_tpl
from gopest.obs import generate_obses_and_ins

import os
import re

PST_BK = './case.pst.backup'
PST = './case.pst'

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

def fix_pcf():
    if not os.path.isfile(PST):
        print('Error: %s does not exist.' % PST)
        exit()
    if os.path.isfile(PST_BK):
        os.remove(PST_BK)
    os.rename(PST, PST_BK)

    try:
        fin = open(PST_BK,'rU')
        pcf_text = fin.read()
        fin.close()

        par_data, n_par = get_lines('pest_par_data')
        obs_data, n_obs = get_lines('pest_obs_data')

        pcf_text = replace_section("* parameter data", "* observation groups",
            pcf_text, par_data)
        pcf_text = replace_section("* observation data", "* model command line",
            pcf_text, obs_data)

        print('+++ found %i parameters and %i observations' % (n_par, n_obs))

        # replace the count of parameters and observations
        def replace_par_obs_cnts(orig):
            """ first two number is n_par and n_obs """
            nums = orig.split()
            return ' '.join([str(n_par), str(n_obs)] + nums[2:])
        pcf_text = replace_nth_line(pcf_text, 4, replace_par_obs_cnts)

        fout = open(PST, 'w')
        fout.write(pcf_text)
        fout.close()
        print('+++ PEST case control file edited, original file saved as %s' % PST_BK)
    except Exception as e:
        print(e)
        print('update_case_pst.py unable to proceed, restoring.')
        os.rename(PST_BK, PST)

def make_case_cli(argv=[]):
    print('make_case_cli', argv)
    # runs goPEST to get par and obs entries
    print('+++ running goPEST to get par and obs')
    generate_params_and_tpl('real_model_original.dat', 'pest_model.tpl', 'pest_par_data')
    generate_obses_and_ins('g_real_model.dat', 'real_model_original_pr.json', 'pest_model.ins', 'pest_obs_data')

    # unfortunately I need to use 'real_model_original_pr.dat' here because it
    # has many GENERs that may not exist in natural state, while still being
    # needed in observations, eg. Production gener's block, hopefully this is
    # okay because we usually don't need to get any actual values out of the
    # real_model_original_pr.dat model.

    # edit them into PEST case control file
    fix_pcf()




