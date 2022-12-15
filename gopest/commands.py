import sys
import gopest.par
import gopest.obs
import gopest.pest_model
import gopest.run_ns_pr
import gopest.submit_beopest
import gopest.make_case_pst

title = """goPEST - Interfacing PEST with Waiwera and (AU)TOUGH2 simulators
"""
hlp = """Use:
    gopest COMMAND [ARGUMENTS]

Supported COMMANDs:
    help
    init             (make_case_pst)
    submit           (submit_beopest)
xx  run              (run_beopest)
    par              (goPESTpar)
    obs              (goPESTobs)
    run-pest-model   (pest_model)
    run-ns-pr        (run_ns_pr)

Important files for goPEST to work:
    goPESTconfig.toml
        This is the main configuration file.
    goPESTpar.list
        This controls model parameters included for PEST.
    goPESTobs.list
        This controls observations for PEST.

University of Auckland, 2012, 2022
"""

def gopest_cli():
    argc = len(sys.argv)
    if argc < 2:
        print(title + hlp)
    else:
        cmds = {
            'par': gopest.par.goPESTpar,
            'obs': gopest.obs.goPESTobs,
            'run-pest-model': gopest.pest_model.main_cli,
            'run-ns-pr': gopest.run_ns_pr.main_cli,
            'submit': gopest.submit_beopest.submit_cli,
            'init': gopest.make_case_pst.make_case_cli,
        }
        if sys.argv[1] == 'help' or sys.argv[1] not in cmds:
            print(title + hlp)
        else:
            print(title)
            cmds[sys.argv[1]](*sys.argv[2:])
