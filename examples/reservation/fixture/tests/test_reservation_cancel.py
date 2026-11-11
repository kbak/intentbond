import unittest

from api import execute


class Spec(unittest.TestCase):
    # [utest~reservation-cancel-check~1->req~reservation-cancel~1]
    def test_rule(self):
        out = execute(
            {
                "capacity": 1,
                "operations": [
                    {"op": "reserve", "key": "a", "qty": 1},
                    {"op": "cancel", "key": "a"},
                    {"op": "reserve", "key": "b", "qty": 1},
                ],
            }
        )
        self.assertEqual([x["result"]["status"] for x in out], [200, 200, 200])
        self.assertEqual(out[-1]["state"]["active"], {"b": 1})
