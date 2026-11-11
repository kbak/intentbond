import unittest

from entrypoint import evaluate


class Spec(unittest.TestCase):
    # [utest~form-label-check~2->req~form-label~2]
    def test_rule(self):
        self.assertEqual(evaluate({"value": "Ada"})["component"]["label"], "Continue")
