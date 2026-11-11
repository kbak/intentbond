import unittest

from api import execute


class Spec(unittest.TestCase):
    # [utest~reservation-idempotency-check~1->req~reservation-idempotency~1]
    def test_rule(self):
        out = execute(
            {
                "capacity": 3,
                "operations": [
                    {"op": "reserve", "key": "a", "qty": 1},
                    {"op": "reserve", "key": "a", "qty": 1},
                ],
            }
        )
        self.assertEqual(out[0], out[1])
