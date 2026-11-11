import unittest

from api import execute


class Spec(unittest.TestCase):
    # [utest~reservation-atomic-check~1->req~reservation-atomic~1]
    def test_rule(self):
        out = execute(
            {
                "capacity": 2,
                "operations": [
                    {"op": "reserve", "key": "a", "qty": 1},
                    {"op": "reserve", "key": "b", "qty": 0},
                ],
            }
        )
        self.assertEqual(out[0]["state"], out[1]["state"])
        self.assertEqual(out[1]["result"]["status"], 400)
