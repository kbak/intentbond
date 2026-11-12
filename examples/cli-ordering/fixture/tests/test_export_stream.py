import json
import unittest

from commands import run


class Spec(unittest.TestCase):
    # [utest~export-stream-check~1->req~export-stream~1]
    def test_rule(self):
        result = run(["--stream"], [{"name": "b", "qty": 2}, {"name": "a", "qty": 1}])
        self.assertEqual(result["code"], 0)
        self.assertEqual(
            [json.loads(line) for line in result["out"].splitlines()],
            [{"name": "a", "qty": 1}, {"name": "b", "qty": 2}],
        )
        self.assertEqual(run(["--stream", "--json"], [])["code"], 2)
