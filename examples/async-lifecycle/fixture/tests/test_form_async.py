import unittest

from entrypoint import evaluate


class Spec(unittest.TestCase):
    # [utest~form-async-check~1->req~form-async~1]
    def test_rule(self):
        result = evaluate({"async": [{"value": "Ada", "delay": 0}]})
        self.assertEqual(result["error"], None)
        self.assertFalse(result["pending"])
