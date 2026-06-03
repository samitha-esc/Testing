import unittest
from engines.engine_medipipe import MediPipeEngine


class TestMediPipe(unittest.TestCase):
    def test_inheritance(self):
        eng = MediPipeEngine()
        self.assertTrue(hasattr(eng, 'process_frame'))


if __name__ == "__main__":
    unittest.main()
