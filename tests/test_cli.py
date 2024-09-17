import unittest
import subprocess
import os

TESTDIR_EMPTY = './tests/data/test_empty_dir'

class TestCLI_NoConfig(unittest.TestCase):
    def setUp(self):
        self.original_dir = os.getcwd()
        os.chdir(TESTDIR_EMPTY)

    def tearDown(self):
        os.chdir(self.original_dir)

    def test_help_command(self):
        expected_output_components = [
            'Version: (',
            'Supported COMMANDs:',
            'help',
            'init [--no-copy][--no-par][--no-obs]',
            'submit',
            'run',
            'par',
            'obs',
            'run-pest-model',
            'run-forward',
            'save-iter-files',
            'check-slaves',
            'Important files for goPEST to work:',
            'goPESTconfig.toml',
            'goPESTpar.list',
            'goPESTobs.list',
            'University of Auckland, 2012, 2022',
        ]
        result = subprocess.run(['gopest'], capture_output=True, text=True)
        for exp in expected_output_components:
            self.assertIn(exp, result.stdout)
        result = subprocess.run(['gopest', 'help'], capture_output=True, text=True)
        for exp in expected_output_components:
            self.assertIn(exp, result.stdout)

if __name__ == '__main__':
    unittest.main()
