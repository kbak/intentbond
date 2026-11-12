"""Keep D3's missed stable-order requirement and independent labels executable."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/cli-ordering"


class CliOrderingExampleTests(unittest.TestCase):
    def script(self, code, *args):
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                "import sys; sys.path.insert(0,sys.argv[1]);\n" + code,
                str(EXAMPLE),
                *map(str, args),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_retained_labels_and_independent_negative_outputs(self):
        # [utest->req~ib-repair-cases~1]
        result = self.script("import json, ordering_profile as p; print(json.dumps(p.qualify()))")
        self.assertEqual(result["cases"], 280)
        self.assertEqual(result["negative_outputs"], 4)
        self.assertEqual(result["minimal_tie_regressions"], 3)

    def test_changed_contract_and_conflicting_or_missing_reference_fail_closed(self):
        # [utest->req~ib-repair-cases~1]
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            shutil.copyfile(EXAMPLE / "fixture/requirements.md", source / "requirements.md")
            result = self.script(
                """
import json
from pathlib import Path
from unittest.mock import patch
import ordering_profile as p
source = Path(sys.argv[2])
assert len(p.validate_contract(source)) == 5
path = source / 'requirements.md'
path.write_text(path.read_text() + '\\nEqual names may be reordered.\\n')
failures=[]
try: p.validate_contract(source)
except ValueError: failures.append('changed')
with patch.object(p.references, 'contract_accepts', return_value=False):
    try: p.generate('initial')
    except ValueError: failures.append('conflict')
with patch.object(p.reference_insertion, 'export_model', side_effect=OSError('unavailable')):
    try: p.generate('initial')
    except OSError: failures.append('missing')
print(json.dumps(failures))
""",
                source,
            )
            self.assertEqual(result, ["changed", "conflict", "missing"])

    def test_json_normalization_preserves_exactly_one_final_line_break(self):
        # [utest->req~ib-repair-cases~1]
        result = self.script(
            r"""
import json
from observation import decode
from references import contract_accepts
case = {"args": ["--json"], "rows": []}
results = []
for output in ("[]\n", "[\n]\n", " [] \t\n", "[]\r\n", "[]", "[]\n\n", "[]\n \t\n"):
    value = {"code": 0, "out": output, "err": ""}
    try:
        decode(case, value)
        accepted = True
    except ValueError:
        accepted = False
    results.append([accepted, contract_accepts(case, value)])
print(json.dumps(results))
"""
        )
        self.assertEqual(result, [[True, True]] * 4 + [[False, False]] * 3)

    def test_original_tests_miss_bug_and_retained_cases_catch_it(self):
        # [utest->req~ib-repair-regressions~1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            shutil.copytree(EXAMPLE / "fixture", source)
            old = subprocess.run(
                [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"],
                cwd=source,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(old.returncode, 0, old.stderr)
            self.assertIn("Ran 5 tests", old.stderr)
            result = self.script(
                """
import json, subprocess
from pathlib import Path
import ordering_profile as p
from demo_actor import proposal
root = Path(sys.argv[2]); path = root/'formatters.py'; original=path.read_text()
cases = p.generate('initial') + p.generate('adversarial')
(root/p.REGRESSION['test_path']).write_text(p.scaffold(p.REGRESSION))
(root/p.REGRESSION['data_path']).write_text(json.dumps(cases))
results={}
for mode in ('original','repair','alternative','two-round','drop-duplicates','reject-duplicates','quantities','pretty-json','json-blank-line'):
    text = original if mode == 'original' else proposal(original,mode,1)
    if mode == 'pretty-json': text=text.replace('separators=(",", ":")','indent=2',1)
    path.write_text(text)
    if mode == 'json-blank-line':
        old = subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_export_*.py'],cwd=root,capture_output=True,text=True,timeout=20)
        assert old.returncode == 0, old.stderr
    run=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_cli_ordering_regression.py'],cwd=root,capture_output=True,text=True,timeout=20)
    results[mode]=run.returncode==0
print(json.dumps(results))
""",
                source,
            )
            self.assertEqual(
                result, {mode: mode in ("repair", "alternative", "pretty-json") for mode in result}
            )

    def test_demo_refuses_disabled_assertions_and_checkout_output(self):
        for args, message in (
            (["-O", "-B", str(EXAMPLE / "demo.py"), "--references-only"], "without -O"),
            (
                ["-B", str(EXAMPLE / "demo.py"), "--out", str(EXAMPLE / "must-not-exist")],
                "outside the source checkout",
            ),
        ):
            result = subprocess.run(
                [sys.executable, *args], capture_output=True, text=True, timeout=20
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(message, result.stderr)
        self.assertFalse((EXAMPLE / "must-not-exist").exists())
