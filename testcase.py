import unittest
from helperstuff import HelperClass


class TestHelperClass(unittest.TestCase):
    def test_my_func(self):
        output = HelperClass.my_func(*([55],), **{})
        assert output == [55, 3]


if __name__ == '__main__':
    unittest.main()
