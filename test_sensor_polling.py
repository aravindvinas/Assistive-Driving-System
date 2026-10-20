import unittest

from sensor_polling import SlidingWindow


class TestSlidingWindow(unittest.TestCase):

    def setUp(self):
        self.window = SlidingWindow(3) 

    def test_update_single_value(self):
        self.window.update(10)
        self.assertEqual(self.window.window, [10])

    def test_window_fills_up(self):
        self.window.update(10)
        self.window.update(20)
        self.window.update(30)
        self.assertEqual(self.window.window, [10, 20, 30])

    def test_oldest_value_is_removed(self):
        self.window.update(10)
        self.window.update(20)
        self.window.update(30)
        self.window.update(40)
        self.assertEqual(self.window.window, [20, 30, 40])

    def test_window_size_remains_fixed(self):
        for value in range(10):
            self.window.update(value)

        self.assertEqual(len(self.window.window), 3)
        self.assertEqual(self.window.window, [7, 8, 9])

    def test_window_with_duplicate_values(self):
        self.window.update(5)
        self.window.update(5)
        self.window.update(5)
        self.window.update(8)
        self.assertEqual(self.window.window, [5, 5, 8])


if __name__ == "__main__":
    unittest.main(verbosity=2)