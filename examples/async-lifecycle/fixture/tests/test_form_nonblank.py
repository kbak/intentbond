import unittest

from entrypoint import evaluate


class Spec(unittest.TestCase):
    # [utest~form-nonblank-check~1->req~form-nonblank~1]
    def test_rule(self):
        self.assertFalse(evaluate({"value": "   "})["response"]["ok"])
        self.assertTrue(evaluate({"value": "Ada"})["response"]["ok"])
