import unittest

from commands import run


class Spec(unittest.TestCase):
    # [utest~export-order-check~1->req~export-order~1]
    def test_rule(self):
        rows = [{"name": "z", "qty": 2}, {"name": "a", "qty": 1}]
        self.assertEqual(run([], rows)["out"], "a\t1\nz\t2\n")
