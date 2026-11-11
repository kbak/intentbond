import unittest

from api import execute


class Spec(unittest.TestCase):
    # [utest~reservation-capacity-check~1->req~reservation-capacity~1]
    def test_rule(self):
        out = execute(
            {
                "capacity": 2,
                "operations": [
                    {"op": "reserve", "key": "a", "qty": 2},
                    {"op": "reserve", "key": "b", "qty": 1},
                ],
            }
        )
        self.assertEqual([x["result"]["status"] for x in out], [200, 409])
