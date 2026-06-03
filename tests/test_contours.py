import unittest
from engines.engine_contours import ContoursEngine


class TestContours(unittest.TestCase):
    def test_inheritance(self):
        eng = ContoursEngine()
        self.assertTrue(hasattr(eng, 'process_frame'))


if __name__ == "__main__":
    unittest.main()
