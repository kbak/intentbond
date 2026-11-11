import unittest

from entrypoint import evaluate


class Spec(unittest.TestCase):
    # [utest~form-wire-check~1->req~form-wire~1]
    def test_rule(self):
        result = evaluate({"value": "Ada"})
        self.assertEqual(result["payload"], {"display_name": "Ada"})
        self.assertEqual(result["component"]["name"], "display_name")
        self.assertEqual(result["response"], {"ok": True, "field": "display_name", "error": None})
