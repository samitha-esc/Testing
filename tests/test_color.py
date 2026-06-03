import unittest
from engines.engine_color import ColorEngine


class TestColor(unittest.TestCase):
    def test_inheritance(self):
        eng = ColorEngine()
        self.assertTrue(hasattr(eng, 'process_frame'))


if __name__ == "__main__":
    unittest.main()
