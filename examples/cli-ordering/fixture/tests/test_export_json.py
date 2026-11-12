import json
import unittest

from commands import run


class Spec(unittest.TestCase):
    # [utest~export-json-check~1->req~export-json~1]
    def test_rule(self):
        self.assertEqual(
            json.loads(run(["--json"], [{"name": "z", "qty": 2}, {"name": "a", "qty": 1}])["out"]),
            [{"name": "a", "qty": 1}, {"name": "z", "qty": 2}],
        )
        self.assertEqual(run(["--json"], [])["code"], 0)
