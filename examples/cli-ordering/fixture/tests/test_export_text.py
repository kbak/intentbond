import unittest

from commands import run


class Spec(unittest.TestCase):
    # [utest~export-text-check~1->req~export-text~1]
    def test_rule(self):
        self.assertEqual(
            run([], [{"name": "tea", "qty": 2}]), {"code": 0, "out": "tea\t2\n", "err": ""}
        )
        self.assertEqual(run([], []), {"code": 0, "out": "", "err": ""})
