import unittest

from commands import run


class Spec(unittest.TestCase):
    # [utest~export-errors-check~1->req~export-errors~1]
    def test_rule(self):
        self.assertEqual(run(["--unknown"], []), {"code": 2, "out": "", "err": "invalid options\n"})
