import copy
import hashlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

from intentbond.common import CheckError
from intentbond.validation_contract import (
    assert_validation_case,
    generate_validation_cases,
    render_validation_tests,
)


def contract():
    return {
        "schema_version": 1,
        "requirement": "req~sample-validation~1",
        "preserve_input": True,
        "output": "normalized",
        "rejection": "ValueError",
        "input": {
            "type": "object",
            "nullable": False,
            "properties": {
                "name": {
                    "required": True,
                    "schema": {
                        "type": "string",
                        "nullable": False,
                        "min_length": 1,
                        "max_length": 4,
                        "alphabet": "ab-",
                        "initial": "ab",
                    },
                },
                "options": {
                    "required": False,
                    "default": {},
                    "schema": {
                        "type": "object",
                        "nullable": False,
                        "properties": {
                            "enabled": {
                                "required": False,
                                "default": True,
                                "schema": {"type": "boolean", "nullable": False},
                            },
                            "retries": {
                                "required": False,
                                "default": 3,
                                "schema": {"type": "integer", "nullable": True, "min": 2, "max": 5},
                            },
                        },
                    },
                },
            },
        },
    }


def valid_options(value):
    """Independent imperative implementation, not the schema interpreter."""
    if type(value) is not dict or value.keys() - {"name", "options"} or "name" not in value:
        raise ValueError("object")
    name = value["name"]
    if (
        type(name) is not str
        or not 1 <= len(name) <= 4
        or name[0] not in "ab"
        or any(c not in "ab-" for c in name)
    ):
        raise ValueError("name")
    options = value.get("options", {})
    if type(options) is not dict or options.keys() - {"enabled", "retries"}:
        raise ValueError("options")
    enabled, retries = options.get("enabled", True), options.get("retries", 3)
    if type(enabled) is not bool:
        raise ValueError("enabled")
    if retries is not None and (type(retries) is not int or not 2 <= retries <= 5):
        raise ValueError("retries")
    return {"name": name, "options": {"enabled": enabled, "retries": retries}}


class ValidationContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "contract.json"

    def save(self, value=None, raw=None):
        self.path.write_text(
            json.dumps(contract() if value is None else value) if raw is None else raw,
            encoding="utf-8",
        )
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def cases(self, value=None, **kwargs):
        return generate_validation_cases(self.path, self.save(value), **kwargs)["cases"]

    # [utest->req~ib-validation-contract-generation~1]
    def test_frozen_boundaries_and_missing_defaults(self):
        cases = self.cases()
        observations = {json.dumps(c["input"], sort_keys=True): c for c in cases}
        minimal = observations[json.dumps({"name": "a"}, sort_keys=True)]
        self.assertEqual(
            minimal["expected"], {"name": "a", "options": {"enabled": True, "retries": 3}}
        )
        for retries, accepted in [
            (None, True),
            (2, True),
            (5, True),
            (1, False),
            (6, False),
            (True, False),
            (1.0, False),
        ]:
            sample = {"name": "a", "options": {"enabled": False, "retries": retries}}
            case = observations[json.dumps(sample, sort_keys=True)]
            self.assertEqual(case["outcome"], "accept" if accepted else "reject")
            if accepted:
                self.assertEqual(case["expected"], sample)
        for value in (
            {},
            {"name": "", "options": {"enabled": False, "retries": 2}},
            {"name": "aaaaa", "options": {"enabled": False, "retries": 2}},
        ):
            self.assertEqual(observations[json.dumps(value, sort_keys=True)]["outcome"], "reject")

    # [utest->req~ib-validation-contract-generation~1]
    def test_digest_determinism_duplicates_and_caps(self):
        pin = self.save()
        first = generate_validation_cases(self.path, pin)
        self.assertEqual(first, generate_validation_cases(self.path, pin))
        self.assertFalse(first["semantic_approval"])
        self.assertEqual(
            len({json.dumps(c["input"], sort_keys=True) for c in first["cases"]}),
            len(first["cases"]),
        )
        with self.assertRaises(CheckError):
            generate_validation_cases(self.path, pin, max_cases=1)
        for cap in (True, 0, 1025):
            with self.assertRaises(CheckError):
                generate_validation_cases(self.path, pin, max_cases=cap)
        self.path.write_text(self.path.read_text() + " ")
        with self.assertRaises(CheckError):
            generate_validation_cases(self.path, pin)
        pin = self.save(raw='{"schema_version":1,"schema_version":1}')
        with self.assertRaises(CheckError):
            generate_validation_cases(self.path, pin)
        pin = self.save(raw=" " * 65537)
        with self.assertRaises(CheckError):
            generate_validation_cases(self.path, pin)

    # [utest->req~ib-validation-contract-generation~1]
    def test_rejects_unsupported_or_ambiguous_contracts(self):
        variants = []
        for field, value in (
            ("approved", True),
            ("output", "infer"),
            ("rejection", "Exception"),
            ("schema_version", True),
            ("requirement", "unreviewed"),
        ):
            c = contract()
            c[field] = value
            variants.append(c)
        for change in (
            {"pattern": "a+"},
            {"type": "array"},
            {"nullable": 0},
            {"initial": "z"},
            {"max_length": 0},
        ):
            c = contract()
            c["input"]["properties"]["name"]["schema"].update(change)
            variants.append(c)
        c = contract()
        c["input"]["properties"]["name"]["default"] = "a"
        variants.append(c)
        c = contract()
        c["input"]["properties"]["options"]["default"] = {"retries": True}
        variants.append(c)
        c = contract()
        child = c["input"]
        for _ in range(6):
            child["properties"]["nested"] = {
                "required": True,
                "schema": {"type": "object", "nullable": False, "properties": {}},
            }
            child = child["properties"]["nested"]["schema"]
        variants.append(c)
        for c in variants:
            with self.subTest(contract=c), self.assertRaises(CheckError):
                self.cases(c)

    # [utest->req~ib-validation-contract-execution~1]
    def test_accepts_independent_valid_implementation_and_reordered_outputs(self):
        cases = self.cases()
        for case in cases:
            assert_validation_case(valid_options, case)
            assert_validation_case(lambda v: dict(reversed(list(valid_options(v).items()))), case)

    # [utest->req~ib-validation-contract-execution~1]
    def test_detects_regressions_and_mutation_on_success_and_rejection(self):
        def wrong_default(v):
            result = valid_options(v)
            if "options" not in v:
                result["options"]["retries"] = 4
            return result

        def null_replaced(v):
            result = valid_options(v)
            if result["options"]["retries"] is None:
                result["options"]["retries"] = 3
            return result

        def mutate_valid(v):
            result = valid_options(v)
            v["name"] = "b"
            return result

        def mutate_invalid(v):
            try:
                return valid_options(v)
            except ValueError:
                if type(v) is dict:
                    v["side_effect"] = True
                raise

        def bool_as_int_output(v):
            result = valid_options(v)
            result["options"]["enabled"] = int(result["options"]["enabled"])
            return result

        for target in (
            wrong_default,
            null_replaced,
            mutate_valid,
            mutate_invalid,
            bool_as_int_output,
        ):
            failures = []
            for case in self.cases():
                try:
                    assert_validation_case(target, case)
                except AssertionError as exc:
                    failures.append(str(exc))
            self.assertTrue(failures, target.__name__)

    # [utest->req~ib-validation-contract-generation~1]
    # [utest->req~ib-validation-contract-execution~1]
    def test_map_null_mixes_and_nonnull_sibling_validation(self):
        c = contract()
        c["input"]["properties"] = {
            "global": {
                "required": True,
                "schema": {"type": "integer", "nullable": True, "min": 1, "max": 5},
            },
            "overrides": {
                "required": True,
                "schema": {
                    "type": "map",
                    "nullable": False,
                    "keys": {
                        "type": "string",
                        "nullable": False,
                        "min_length": 1,
                        "max_length": 3,
                        "alphabet": "ab-",
                        "initial": "ab",
                    },
                    "values": {"type": "integer", "nullable": True, "min": 1, "max": 5},
                },
            },
        }
        cases = self.cases(c)
        self.assertTrue(
            any(
                x["outcome"] == "accept"
                and x["input"] == {"global": 1, "overrides": {"a": None, "b": 1}}
                for x in cases
            )
        )
        self.assertTrue(
            any(
                x["outcome"] == "reject" and x["input"] == {"global": None, "overrides": {"a": 6}}
                for x in cases
            )
        )
        self.assertTrue(
            any(
                x["outcome"] == "reject"
                and x["input"] == {"global": 1, "overrides": {"a": None, "b": 6}}
                for x in cases
            )
        )

    # [utest->req~ib-validation-contract-generation~1]
    # [utest->req~ib-validation-contract-execution~1]
    def test_strict_types_inside_range_and_fixed_length_interior(self):
        c = contract()
        c["input"] = {"type": "integer", "nullable": False, "min": 20, "max": 30}
        cases = self.cases(c)
        case = next(x for x in cases if type(x["input"]) is float and x["input"] == 20.0)
        self.assertEqual(case["outcome"], "reject")
        with self.assertRaises(AssertionError):
            assert_validation_case(lambda v: v, case)
        c["input"] = {
            "type": "string",
            "nullable": False,
            "min_length": 3,
            "max_length": 3,
            "alphabet": "ab-",
            "initial": "ab",
        }
        cases = self.cases(c)
        interior = next(x for x in cases if x["input"] == "aaé")
        self.assertEqual(interior["outcome"], "reject")
        with self.assertRaises(AssertionError):
            assert_validation_case(lambda v: v, interior)

    # [utest->req~ib-validation-contract-generation~1]
    # [utest->req~ib-validation-contract-execution~1]
    def test_unrestricted_unicode_nullable_root_and_absent_optional_field(self):
        c = contract()
        c["input"] = {"type": "string", "nullable": True, "min_length": 0, "max_length": 4}

        def validate(v):
            if v is not None and (type(v) is not str or len(v) > 4):
                raise ValueError()
            return v

        cases = self.cases(c)
        for case in cases:
            assert_validation_case(validate, case)
        self.assertTrue(any(x["input"] == "é" and x["outcome"] == "accept" for x in cases))
        c = contract()
        c["input"]["properties"]["options"].pop("default")
        case = next(x for x in self.cases(c) if x["input"] == {"name": "a"})
        self.assertEqual(case["expected"], {"name": "a"})

    # [utest->req~ib-validation-contract-execution~1]
    def test_runtime_errors_and_async_are_not_success(self):
        reject = next(x for x in self.cases() if x["outcome"] == "reject")

        def broken(_):
            raise RuntimeError("not validation")

        async def asynchronous(_):
            return None

        with self.assertRaises(RuntimeError):
            assert_validation_case(broken, reject)
        with self.assertRaises(AssertionError):
            assert_validation_case(asynchronous, reject)
        allow_mutation = copy.deepcopy(reject)
        allow_mutation.update(input={}, preserve_input=False)

        def declared_mutation(v):
            v["mutated"] = True
            raise ValueError()

        assert_validation_case(declared_mutation, allow_mutation)

    # [utest->req~ib-validation-contract-generation~1]
    # [utest->req~ib-validation-contract-execution~1]
    def test_renders_runnable_tests_without_importing_candidate(self):
        pin = self.save()
        source = render_validation_tests(self.path, pin, module="not_installed", function="check")
        compile(source, "generated.py", "exec")
        module = types.ModuleType("contract_test_target")
        module.check = valid_options
        sys.modules[module.__name__] = module
        self.addCleanup(sys.modules.pop, module.__name__)
        source = render_validation_tests(self.path, pin, module=module.__name__, function="check")
        namespace = {}
        exec(compile(source, "generated.py", "exec"), namespace)
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(
            namespace["ValidationContractTests"]
        )
        result = unittest.TestResult()
        suite.run(result)
        self.assertTrue(result.wasSuccessful(), (result.errors, result.failures))
        self.assertGreater(result.testsRun, 0)
        for module_name, function_name in (
            ("x;exit()", "check"),
            ("x", "class"),
            ("x", "object.check"),
        ):
            with self.assertRaises(CheckError):
                render_validation_tests(self.path, pin, module=module_name, function=function_name)

    # [utest->req~ib-validation-contract-generation~1]
    def test_rendered_contract_text_remains_data(self):
        c = contract()
        c["input"]["properties"]["quote'\"\n# data"] = c["input"]["properties"].pop("name")
        pin = self.save(c)
        source = render_validation_tests(self.path, pin, module="not_installed", function="check")
        compile(source, "generated.py", "exec")
        self.assertIn("\n", source.split("BUNDLE = ", 1)[1].split("TARGET =", 1)[0])
