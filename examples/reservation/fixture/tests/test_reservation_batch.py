import unittest

from api import execute


class Spec(unittest.TestCase):
    # [utest~reservation-batch-check~1->req~reservation-batch~1]
    def test_rule(self):
        out = execute(
            {
                "capacity": 3,
                "operations": [
                    {"op": "batch", "items": [{"key": "a", "qty": 1}, {"key": "b", "qty": 2}]}
                ],
            }
        )
        self.assertEqual(out[0]["result"]["status"], 200)
        self.assertEqual(out[0]["state"]["active"], {"a": 1, "b": 2})
