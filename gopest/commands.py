import sys

from gopest import __version__

title = """
goPEST - Interfacing PEST with Waiwera and (AU)TOUGH2 simulators
"""

version = """Version: (%s)
""" % __version__

hlp = """
Usage: gopest COMMAND [ARGUMENTS]

Supported COMMANDs:
    help
    init [--no-copy][--no-par][--no-obs]    (make_case_pst)
    submit                                  (submit_beopest)
xx  run                                     (run_beopest)
    par                                     (goPESTpar)
    obs                                     (goPESTobs)
    run-pest-model                          (pest_model)
    run-forward                             (run_ns_pr)
    save-iter-files                         (rename_latest_files)
    check-slaves                            (check_slaves)

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
    print(title)
    argc = len(sys.argv)
    if argc < 2:
        print(version + hlp)
    else:
        if sys.argv[1] == 'help':
            print(version + hlp)
        else:
            # NOTE loading gopest.common checks goPESTconfig.toml
            import gopest.common
            import gopest.par
            import gopest.obs
            import gopest.pest_model
            import gopest.run_ns_pr
            import gopest.submit_beopest
            import gopest.make_case_pst
            import gopest.rename_latest_files
            import gopest.check_slaves
            cmds = {
                'par': gopest.par.goPESTpar,
                'obs': gopest.obs.goPESTobs,
                'run-pest-model': gopest.pest_model.main_cli,
                'run-forward': gopest.run_ns_pr.main_cli,
                'submit': gopest.submit_beopest.submit_cli,
                'init': gopest.make_case_pst.make_case_cli,
                'save-iter-files': gopest.rename_latest_files.rename_latest_files,
                'check-slaves': gopest.check_slaves.check_slaves_cli,
            }
            if sys.argv[1] not in cmds:
                print(version + hlp)
                print('Error! COMMAND not recognised.')
                exit(1)
            cmds[sys.argv[1]](sys.argv[1:])

"""
- NOTE good reference on designing CLI command names:
  https://smallstep.com/blog/the-poetics-of-cli-command-names/

- TODO it's probably not necessary to have so many commands
"""
