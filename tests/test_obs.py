import unittest
import os
from pprint import pprint as pp

from mulgrids import *
from t2data import *
from t2listing import *

TESTDIR = './tests/data'

class TestObsDefs(unittest.TestCase):
    """ Test goPESTobs type by type, from users perspective. """
    def setUp(self):
        self.original_dir = os.getcwd()
        os.chdir(TESTDIR)

        self.geo = mulgrid("./gwai6307_06.dat")
        self.dat = t2data("./wai6307ns_021.dat")
        self.lst = t2listing("./wai6307ns_021.listing")

    def tearDown(self):
        del self.geo
        del self.dat
        self.lst.close()
        del self.lst
        os.chdir(self.original_dir)

    def test_totalheat_modelresult(self):
        """ totalheat should handle fixed/unfixed name even with regular expression """
        def fixname_and_re_problem(gnames):
            from gopest.obs import UserEntryObserv, OBS_USER_FUNC
            obsType = 'totalheat'
            fieldDataFile, customFilter, offsetTime = '', 'True', 0.0
            obsInfo = ["2000.00"] + gnames
            ue = UserEntryObserv(obsType,obsInfo,fieldDataFile,customFilter,
                offsetTime)

            obfs = OBS_USER_FUNC[ue.obsType+'_modelresult'](self.geo,self.dat,self.lst,ue)
            self.assertEqual(obfs[0], 42586.0, '%s failed to match "RH100"' % str(gnames))

        # all these SHOULD match exactly ONE gener: RH100
        fixname_and_re_problem(["'RH1 0'"])
        fixname_and_re_problem(["'RH(1 0|1 1)'"])
        fixname_and_re_problem(["'RH(100|101)'"])
        fixname_and_re_problem(["'RH1[ 01]0'"])
        fixname_and_re_problem(["'RH1[01]0'"])
        fixname_and_re_problem(["'RH1[ 1]0'"])
        fixname_and_re_problem(["'RH100'","'SO100'"]) # SO is MASS not HEAT

    def test_unique_name(self):
        """ function to generate unique obs names """
        from gopest.obs_def import unique_obs_name
        self.assertEqual("En_EE_45_0001", unique_obs_name("enthalpy", "EE 45"))
        self.assertEqual("En_EE_45_0002", unique_obs_name("enthalpy", "EE 45"))
        self.assertEqual("my_EE456_0001", unique_obs_name("myenthalpy", "EE[456]00"))

    def test_totalheat_raise_exp(self):
        """ totalheat should raise exception when creating obs, if specified geners does not match anything. """
        from gopest.obs import UserEntryObserv, OBS_USER_FUNC
        obsType = 'totalheat'
        fieldDataFile, customFilter, offsetTime = '', 'True', 0.0
        obsInfo = [
            "2000.00",
            "'XX100'",
            "'XX100'",
            "'XX100'",
            "'XX100'",
            "'XX100'",
            "'XX100'",
            ]
        # this should NOT match anything and raise exception
        ue = UserEntryObserv(obsType,obsInfo,fieldDataFile,customFilter,
            offsetTime)

        with self.assertRaises(Exception) as context:
            obss = OBS_USER_FUNC[ue.obsType+'_fielddata'](self.geo,self.dat,ue)
        self.assertTrue('does not match' in str(context.exception))


class FullTest_goPESTobs(unittest.TestCase):
    """ Test running goPESTobs.py as an app, and check basic function """
    def setUp(self):
        self.original_dir = os.getcwd()
        os.chdir(TESTDIR)

    def tearDown(self):
        os.chdir(self.original_dir)

    def generateInput(self, fname, lines):
        f = open(fname, 'w')
        f.write('\n'.join(lines))
        f.close()

    def linesFromOutput(self, fname, cleanup=False):
        """ cleanup=True will have all line ending removed and keeps only non-
        empty lines. """
        f = open(fname, 'r')
        lines = f.readlines()
        f.close()
        if cleanup:
            return [str(line.rstrip()) for line in lines if line.strip()]
        else:
            return lines

    def cleanFiles(self, filenames):
        import glob
        for f in filenames:
            for ff in glob.glob(f):
                os.remove(ff)

    def runFullTest(self, list_lines, ins_lines, obs_lines, obf_lines):
        """ given contents of goPESTobs.list file, goPESTobs.py will be run and
        results compared to expected ins/obs/obf.  Note all expected lines are
        cleaned-up and line endings removed. """
        self.generateInput('goPESTobs.list', list_lines)

        # to generate PEST .pst observation section and .ins:
        #      goPESTobs.py geo dat newPESTins
        # API:
        #      generate_obses_and_ins(fgeo, fdat, insToWrite,
        #                             fobses, fplts='goPESTobs.json', fcovs='goPESTobs.coverage')
        from gopest.obs import generate_obses_and_ins
        generate_obses_and_ins(
            "gwai6307_06.dat",
            "wai6307ns_021.dat",
            "pest_obs_ins",
            "pest_obs")

        ins = self.linesFromOutput("pest_obs_ins", cleanup=True)
        self.assertEqual(ins, ins_lines)
        obs = self.linesFromOutput("pest_obs", cleanup=True)
        self.assertEqual(obs, obs_lines)
        self.cleanFiles(["pest_obs_ins", "pest_obs"])

        # to read Tough2 results and write result file for PEST to read:
        #      goPESTobs.py geo dat lst newPESTobf
        # API:
        #      read_from_real_model(fgeo, fdat, flst, fobf, waiwera=False)
        from gopest.obs import read_from_real_model
        read_from_real_model(
            "gwai6307_06.dat",
            "wai6307ns_021.dat",
            "wai6307ns_021.listing",
            "pest_obs_obf")

        obf = self.linesFromOutput("pest_obs_obf", cleanup=True)
        self.assertEqual(obf, obf_lines)
        self.cleanFiles(["goPESTobs.list", "pest_obs_obf"])

        # TODO: review these additional, possibly some junk
        self.cleanFiles(["goPESTobs.coverage", "goPESTobs.json"])
        self.cleanFiles(["*.obs"])

    def test_totalheat(self):
        self.runFullTest(
            [
                "[ObservationType]",
                "totalheat",
                "",
                "[Defaults]",
                "OBSNME = 'Heat'",
                "OBGNME = 'HtTotal'",
                "",
                "[Obs]",
                "2000.00",
                "'RH100'",
                "",
            ],
            [
                "pif #",
                "l1 [He_RH100_0001]21:41",
            ],
            [
                " He_RH100_0001         2.0000000000000e+03  1.00000e+00 HtTotal",
            ],
            [
                "He_RH100_0001         4.2586000000000e+04",
            ]
            )

    def test_totalupflow(self):
        self.runFullTest(
            [
                "[ObservationType]",
                "totalupflow",
                "",
                "[Defaults]",
                "OBGNME = 'totalupflow'",
                "",
                "[Obs]",
                "1000.00",
                "'SO3 0'",
                "",
                "[Obs]",
                "2000.00",
                "'SO...'",
                "",
            ],
            [
                "pif #",
                "l1 [Uf_SO3_0_0001]21:41",
                "l1 [Uf_SO____0001]21:41",
            ],
            [
                " Uf_SO3_0_0001         1.0000000000000e+03  1.00000e+00 totalupflow",
                " Uf_SO____0001         2.0000000000000e+03  1.00000e+00 totalupflow",
            ],
            [
                "Uf_SO3_0_0001         1.0000000000000e+01",
                "Uf_SO____0001         7.0100000000000e+02",
            ]
            )

    def test_blocktemperature(self):
        self.runFullTest(
            [
                "[ObservationType]",
                "blocktemperature",
                "",
                "[Defaults]",
                "OBSNME = 'TB'",
                "OBGNME = 'TempByBlock'",
                "",
                "[Obs]",
                "'surface'",
                "ex_obs_temp_by_block.dat",
                "",
                "# filter out unwanted blocks",
                "# also supports matching time",
                "[DataFilter]",
                "block not in ['BO993', 'BK900']",
                "[Obs]",
                "'surface', 100.0",
                "ex_obs_temp_by_block.dat",
                "",
            ],
            [
                "pif #",
                "l1 [TB_BO993_0001]21:41",
                "l1 [TB_BK900_0001]21:41",
                "l1 [TB_BJ_10_0001]21:41",
                "l1 [TB_BJ_10_0002]21:41",
            ],
            [
                " TB_BO993_0001         2.5000000000000e+01  1.00000e+00 TempByBlock",
                " TB_BK900_0001         1.0000000000000e+02  1.00000e+00 TempByBlock",
                " TB_BJ_10_0001         5.2000000000000e+01  1.00000e+00 TempByBlock",
                " TB_BJ_10_0002         5.2000000000000e+01  1.00000e+00 TempByBlock",
            ],
            [
                "TB_BO993_0001         1.5785000000000e+02",
                "TB_BK900_0001         4.3913000000000e+01",
                "TB_BJ_10_0001         8.5268000000000e+01",
                "TB_BJ_10_0002         8.5268000000000e+01",
            ]
            )

    def xtest_heatflow(self):
        self.runFullTest(
            [
                "[ObservationType]",
                "heatflow",
                "",
                "[Defaults]",
                "OBSNME = 'Hf'",
                "OBGNME = 'hf'",
                "",
                "# each obs has two lines, first line is zone name, and second",
                "# line is expected value.",
                "[Obs]",
                "'AAA'",
                "100.0",
                "# The zone name should be a string in python style (in quotes),",
                "# which is name of user defined zone (defined in get_surface_heatflow.cfg,",
                "# each zone can be a polygon or a list of columns).  ",
                "",
                "[Obs]",
                "'BBB'",
                "200.0",
                "",
                "[Obs]",
                "'CCC'",
                "300.0",
                "",
            ],
            [
                "pif #",
                "l1 [Hf_AAA_0001]21:41",
                "l1 [Hf_BBB_0001]21:41",
                "l1 [Hf_CCC_0001]21:41",
            ],
            [
                " Hf_AAA_0001           1.0000000000000e+02  1.00000e+00 hf",
                " Hf_BBB_0001           2.0000000000000e+02  1.00000e+00 hf",
                " Hf_CCC_0001           3.0000000000000e+02  1.00000e+00 hf",
            ],
            [
                "Hf_AAA_0001           1.1348649000000e+02",
                "Hf_BBB_0001           8.9901714260000e+03",
                "Hf_CCC_0001           9.1036579160000e+03",
            ]
            )

    def xtest_heatflowminimum(self):
        self.runFullTest(
            [
                "[ObservationType]",
                "heatflowminimum",
                "",
                "[Defaults]",
                "OBSNME = 'Hm'",
                "OBGNME = 'hfmin'",
                "",
                "# each obs has two lines, first line is zone name, and second",
                "# line is expected value.",
                "# The zone name should be a string in python style (in quotes),",
                "# which is name of user defined zone (defined in get_surface_heatflow.cfg,",
                "# each zone can be a polygon or a list of columns).  ",
                "[Obs]",
                "' 90'",
                "100.0",
                # model result is 1.1348649000000e+02
                "",
                "[Obs]",
                "'175'",
                "9000.0",
                # model result is 8.9901714260000e+03
                "",
            ],
            [
                "pif #",
                "l1 [Hm__90_0001]21:41",
                "l1 [Hm_175_0001]21:41",
            ],
            [
                " Hm__90_0001           1.0000000000000e+02  1.00000e+00 hfmin",
                " Hm_175_0001           9.0000000000000e+03  1.00000e+00 hfmin",
            ],
            [
                "Hm__90_0001           1.0000000000000e+02",
                "Hm_175_0001           8.9901714260000e+03",
            ]
            )

    def test_enthalpy(self):
        self.runFullTest(
            [
                "[ObservationType]",
                "enthalpy",
                "",
                "[DataTimeOffset]",
                "1953.0 * 60.0 * 60.0 * 24.0 * 365.25",
                "",
                "[Defaults]",
                "OBSNME = 'En'",
                "OBGNME = 'enth14'",
                "",
                "[DataFilter]",
                "1970.0 <= time <= 1980.0",
                "",
                "[Obs]",
                "'SP 30'",
                "ex_obs_hist.dat",
                "",
                "[Defaults]",
                "OBGNME = 'enth45'",
                "",
                "[DataFilter]",
                "1972.0 <= time",
                "",
                "[Obs]",
                "'RW95[567]'",
                "ex_obs_hist.dat",
                "",
            ],
            [
                "pif #",
                "l1 [En_SP_30_0001]21:41",
                "l1 [En_SP_30_0002]21:41",
                "l1 [En_RW955_0001]21:41",
                "l1 [En_RW955_0002]21:41",
            ],
            [
                " En_SP_30_0001         1.0000000000000e+05  1.00000e+00 enth14",
                " En_SP_30_0002         2.0000000000000e+05  1.00000e+00 enth14",
                " En_RW955_0001         2.0000000000000e+05  1.00000e+00 enth45",
                " En_RW955_0002         3.0000000000000e+05  1.00000e+00 enth45",
            ],
            [
                "En_SP_30_0001         1.0401000000000e+06",
                "En_SP_30_0002         1.0401000000000e+06",
                "En_RW955_0001         8.3950000000000e+04",
                "En_RW955_0002         8.3950000000000e+04",
            ]
            )

    def test_pressure(self):
        self.runFullTest(
            [
                "[ObservationType]",
                "pressure",
                "",
                "[DataTimeOffset]",
                "1953.0 * 60.0 * 60.0 * 24.0 * 365.25",
                "",
                "[Defaults]",
                "OBGNME = 'pressure'",
                "",
                "[DataFilter]",
                "1970.0 <= time <= 1980.0",
                "",
                "[Obs]",
                "'BC2 0'",
                "ex_obs_hist.dat",
                "",
                "[DataFilter]",
                "1972.0 <= time",
                "",
                "[Obs]",
                "'BC195'",
                "ex_obs_hist.dat",
                "",
            ],
            [
                "pif #",
                "l1 [Pr_BC2_0_0001]21:41",
                "l1 [Pr_BC2_0_0002]21:41",
                "l1 [Pr_BC195_0001]21:41",
                "l1 [Pr_BC195_0002]21:41",
            ],
            [
                " Pr_BC2_0_0001         1.0000000000000e+07  1.00000e+00 pressure",
                " Pr_BC2_0_0002         2.0000000000000e+07  1.00000e+00 pressure",
                " Pr_BC195_0001         2.0000000000000e+07  1.00000e+00 pressure",
                " Pr_BC195_0002         3.0000000000000e+07  1.00000e+00 pressure",
            ],
            [
                "Pr_BC2_0_0001         5.5193000000000e+06",
                "Pr_BC2_0_0002         5.5193000000000e+06",
                "Pr_BC195_0001         5.5419000000000e+06",
                "Pr_BC195_0002         5.5419000000000e+06",
            ]
            )

    def test_pressure_by_well(self):
        self.runFullTest(
            [
                "[ObservationType]",
                "pressure_by_well",
                "",
                "[DataTimeOffset]",
                "1953.0 * 60.0 * 60.0 * 24.0 * 365.25",
                "",
                "[Defaults]",
                "OBGNME = 'pressure'",
                "",
                "[DataFilter]",
                "1970.0 <= time <= 1980.0",
                "",
                "[Obs]",
                "'TH  2', -125.0",
                "ex_obs_hist.dat",
                "",
                "[DataFilter]",
                "1972.0 <= time",
                "",
                "[Obs]",
                "'TH  3', -125.0",
                "ex_obs_hist.dat",
                "",
            ],
            [
                "pif #",
                "l1 [Pw_TH__2_0001]21:41",
                "l1 [Pw_TH__2_0002]21:41",
                "l1 [Pw_TH__3_0001]21:41",
                "l1 [Pw_TH__3_0002]21:41",
            ],
            [
                " Pw_TH__2_0001         1.0000000000000e+07  1.00000e+00 pressure",
                " Pw_TH__2_0002         2.0000000000000e+07  1.00000e+00 pressure",
                " Pw_TH__3_0001         2.0000000000000e+07  1.00000e+00 pressure",
                " Pw_TH__3_0002         3.0000000000000e+07  1.00000e+00 pressure",
            ],
            [
                "Pw_TH__2_0001         5.1317000000000e+06", # BC335
                "Pw_TH__2_0002         5.1317000000000e+06", # .
                "Pw_TH__3_0001         5.1267000000000e+06", # BC350
                "Pw_TH__3_0002         5.1267000000000e+06", # .
            ]
            )

    def test_temperature(self):
        self.runFullTest(
            [
                "[ObservationType]",
                "temperature",
                "",
                "[DataTimeOffset]",
                "1953.0 * 60.0 * 60.0 * 24.0 * 365.25",
                "",
                "[Defaults]",
                "OBGNME = 'temperature'",
                "",
                "# Each [Obs] should have exactly TWO lines!",
                "# First line starts with a Well name as python (quoted) string,",
                "#   then followed by the time (number) after comma.",
                "# Second line is the name of the data file, also processed by user routines",
                "#   to become the actual data PEST compare against",
                "",
                "[DataFilter]",
                "elev < 350.0",
                "",
                "[Obs]",
                "'TM  1', 1967.00",
                "ex_obs_temp.dat",
                "",
                "# if time is not specified, 0.0 assumed, okay for NS results with single table ",
                "[Obs]",
                "'TM  2'",
                "ex_obs_temp.dat",
                "",
            ],
            [
                "pif #",
                "l1 [Tw_TM__1_0001]21:41",
                "l1 [Tw_TM__1_0002]21:41",
                "l1 [Tw_TM__1_0003]21:41",
                "l1 [Tw_TM__1_0004]21:41",
                "l1 [Tw_TM__2_0001]21:41",
                "l1 [Tw_TM__2_0002]21:41",
                "l1 [Tw_TM__2_0003]21:41",
                "l1 [Tw_TM__2_0004]21:41",
            ],
            [
                " Tw_TM__1_0001         2.0000000000000e+02  1.00000e+00 temperature",
                " Tw_TM__1_0002         2.0000000000000e+02  1.00000e+00 temperature",
                " Tw_TM__1_0003         2.0000000000000e+02  1.00000e+00 temperature",
                " Tw_TM__1_0004         2.0000000000000e+02  1.00000e+00 temperature",
                " Tw_TM__2_0001         2.0000000000000e+02  1.00000e+00 temperature",
                " Tw_TM__2_0002         2.0000000000000e+02  1.00000e+00 temperature",
                " Tw_TM__2_0003         2.0000000000000e+02  1.00000e+00 temperature",
                " Tw_TM__2_0004         2.0000000000000e+02  1.00000e+00 temperature",
            ],
            [
                "Tw_TM__1_0001         1.2131000000000e+02", # AP530
                "Tw_TM__1_0002         1.6224000000000e+02", # AR530
                "Tw_TM__1_0003         1.8296000000000e+02", # AT530
                "Tw_TM__1_0004         1.9329000000000e+02", # AV530
                "Tw_TM__2_0001         7.2344000000000e+01", # AP680
                "Tw_TM__2_0002         9.2872000000000e+01", # AR680
                "Tw_TM__2_0003         1.0999000000000e+02", # AT680
                "Tw_TM__2_0004         1.2302000000000e+02", # AV680
            ]
            )

    def test_temperature_thickness(self):
        self.runFullTest(
            [
                "[ObservationType]",
                "temperature_thickness",
                "",
                "[DataTimeOffset]",
                "1953.0 * 60.0 * 60.0 * 24.0 * 365.25",
                "",
                "[Defaults]",
                "OBGNME = 'temperature'",
                "",
                "# Each [Obs] should have exactly TWO lines!",
                "# First line starts with a Well name as python (quoted) string,",
                "#   then followed by the time (number) after comma.",
                "# Second line is the name of the data file, also processed by user routines",
                "#   to become the actual data PEST compare against",
                "",
                "[DataFilter]",
                "elev < 350.0",
                "",
                "[Obs]",
                "'TM  1', 1967.00",
                "ex_obs_temp.dat",
                "",
                "# if time is not specified, 0.0 assumed, okay for NS results with single table ",
                "[Obs]",
                "'TM  2'",
                "ex_obs_temp.dat",
                "",
            ],
            [
                "pif #",
                "l1 [Th_TM__1_0001]21:41",
                "l1 [Th_TM__1_0002]21:41",
                "l1 [Th_TM__1_0003]21:41",
                "l1 [Th_TM__1_0004]21:41",
                "l1 [Th_TM__2_0001]21:41",
                "l1 [Th_TM__2_0002]21:41",
                "l1 [Th_TM__2_0003]21:41",
                "l1 [Th_TM__2_0004]21:41",
            ],
            [
                " Th_TM__1_0001         2.0000000000000e+02  5.00000e+01 temperature",
                " Th_TM__1_0002         2.0000000000000e+02  5.00000e+01 temperature",
                " Th_TM__1_0003         2.0000000000000e+02  5.00000e+01 temperature",
                " Th_TM__1_0004         2.0000000000000e+02  5.00000e+01 temperature",
                " Th_TM__2_0001         2.0000000000000e+02  5.00000e+01 temperature",
                " Th_TM__2_0002         2.0000000000000e+02  5.00000e+01 temperature",
                " Th_TM__2_0003         2.0000000000000e+02  5.00000e+01 temperature",
                " Th_TM__2_0004         2.0000000000000e+02  5.00000e+01 temperature",
            ],
            [
                "Th_TM__1_0001         1.2131000000000e+02", # AP530
                "Th_TM__1_0002         1.6224000000000e+02", # AR530
                "Th_TM__1_0003         1.8296000000000e+02", # AT530
                "Th_TM__1_0004         1.9329000000000e+02", # AV530
                "Th_TM__2_0001         7.2344000000000e+01", # AP680
                "Th_TM__2_0002         9.2872000000000e+01", # AR680
                "Th_TM__2_0003         1.0999000000000e+02", # AT680
                "Th_TM__2_0004         1.2302000000000e+02", # AV680
            ]
            )


if __name__ == '__main__':
    """ test a single case by using case name as command argument, eg.:
            python goPESTtest.py FullTest_goPESTobs.test_temperature_thickness
    """
    unittest.main(verbosity=3)
