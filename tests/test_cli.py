import unittest
import subprocess

class TestCLI(unittest.TestCase):
    def test_help_command(self):
        result = subprocess.run(['gopest', 'help'], capture_output=True, text=True)
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
        for exp in expected_output_components:
            self.assertIn(exp, result.stdout)

if __name__ == '__main__':
    unittest.main()
