"""Lean comment boundaries and real OFT imports, without a Lean runtime dependency."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st
from test_workflow import WorkflowFixture

from intentbond.common import CheckError
from intentbond.lean_comments import comment_lines
from intentbond.oft import annotation_diagnostics, import_items

TAG = "[impl->req~session-expiration~1]"
FAKE = "[impl->req~not-a-requirement~1]"


class LeanCommentTests(unittest.TestCase):
    def test_comments_strings_raw_strings_identifiers_and_characters(self):
        source = (
            f'def quoted := "-- {FAKE}"\n'
            f'def raw := r##"" /- {FAKE} -/ "#"##\n'
            f"def «-- {FAKE}» := 0\n"
            "def prime' := '\"'\n"
            f'def interpolated := s!"{{"-- {FAKE}"}}"\n'
            f"-- {TAG}\n"
            f"/- outer /- nested {TAG} -/ tail -/\n"
            f"/-- docs {TAG} -/\n"
            f"/-! module\n{TAG}\n-/\n"
            f"def n := 0 -- {TAG}"
        )
        view, comments = comment_lines(source.encode(), "sample.lean")
        # [utest->req~ib-lean-annotations~1]
        self.assertNotIn(FAKE.encode(), view)
        self.assertEqual(view.count(TAG.encode()), 5)
        self.assertEqual(comments, {6, 7, 8, 9, 10, 12})
        self.assertEqual(view.count(b"\n"), source.count("\n"))

    def test_set_image_notation_and_primed_names_do_not_open_characters(self):
        source = f"def x' := f '' s\ndef y := xs[i]'(by omega)\n-- {TAG}\n"
        view, _ = comment_lines(source.encode(), "image.lean")
        # [utest->req~ib-lean-annotations~1]
        self.assertIn(TAG.encode(), view.split(b"\n")[2])

    def test_physical_lines_bom_and_line_comment_delimiters(self):
        source = f"-- /- ignored block opener\r\n/- {TAG} -/\r-- {TAG}"
        view, _ = comment_lines(b"\xef\xbb\xbf" + source.encode(), "unicode.lean")
        # [utest->req~ib-lean-annotations~1]
        self.assertEqual(view.count(b"\n"), 2)
        self.assertIn(TAG.encode(), view.split(b"\n")[1])
        self.assertIn(TAG.encode(), view.split(b"\n")[2])

    def test_unterminated_boundaries_fail_with_path_and_line(self):
        # [utest->req~ib-lean-annotations~1]
        for source in ("/- open", '"open', 'r#"open', "«open", "'\\u12", 's!"{x'):
            with self.subTest(source=source), self.assertRaisesRegex(CheckError, "broken.lean:2"):
                comment_lines(("\n" + source).encode(), "broken.lean")
        with self.assertRaisesRegex(CheckError, "broken.lean"):
            comment_lines(b"\xff", "broken.lean")

    def test_interpolation_comments_and_nested_strings_keep_lexical_boundaries(self):
        source = (
            f'def x := s! /- prefix -/ "{{let y := m!"{{"-- {FAKE}"}}";\n'
            f'/- {TAG} -/ y}}"\n'
            f'def y := "escaped \\" -- {FAKE} \\""\n'
            f'def z := "gap \\\n-- {FAKE}"\n'
        )
        view, _ = comment_lines(source.encode(), "interpolation.lean")
        # [utest->req~ib-lean-annotations~1]
        self.assertNotIn(FAKE.encode(), view)
        self.assertEqual(view.count(TAG.encode()), 1)
        self.assertIn(TAG.encode(), view.split(b"\n")[1])

    @settings(max_examples=50, database=None, derandomize=True, deadline=None)
    @given(depth=st.integers(1, 20), padding=st.integers(0, 12), hashes=st.integers(0, 8))
    def test_nested_comments_preserve_tags_and_raw_strings_never_supply_them(
        self, depth, padding, hashes
    ):
        source = (
            "r"
            + "#" * hashes
            + '"'
            + FAKE
            + '"'
            + "#" * hashes
            + "\n" * padding
            + "/- " * depth
            + TAG
            + " -/" * depth
        )
        view, _ = comment_lines(source.encode(), "generated.lean")
        # [utest->req~ib-lean-annotations~1]
        self.assertNotIn(FAKE.encode(), view)
        self.assertEqual(view.count(TAG.encode()), 1)
        self.assertIn(TAG.encode(), view.split(b"\n")[padding])


class LeanImportTests(WorkflowFixture):
    def lean_source(self, content):
        path = self.repo / "source with spaces.lean"
        path.write_text(content)
        self.configure(lambda scope: scope["inputs"].append(path.name))
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        return path

    def test_real_oft_imports_all_comment_forms_with_original_locations(self):
        source = (
            f'def example := "{FAKE}"\n'
            f"-- {TAG}\n"
            f"/- {TAG} -/\n"
            f"/-- {TAG} -/\n"
            f"/-!\n{TAG}\n-/\n"
            f"/- /- {TAG} -/ -/\n"
            "-- [utest->req~session-expiration~1]\n"
        )
        path = self.lean_source(source)
        result = self.run_check()
        # [utest->req~ib-lean-annotations~1]
        self.assertEqual(result["status"], "passed", result)
        items = import_items(self.out / "candidate-items.xml", self.repo)
        lean = [item for item in items if item["path"] == path.name]
        self.assertEqual([item["line"] for item in lean if item["type"] == "impl"], [2, 3, 4, 6, 8])
        self.assertEqual([item["line"] for item in lean if item["type"] == "utest"], [9])
        self.assertEqual(path.read_text(), source)
        self.assertEqual(
            (self.out / "base-items.xml").read_bytes(),
            (self.out / "candidate-items.xml").read_bytes(),
        )

    def test_missing_requirement_and_stale_revision_fail_check(self):
        self.lean_source(f"/-! {TAG} -/\n")
        # [utest->req~ib-lean-annotations~1]
        for tag in (FAKE, TAG.replace("~1]", "~2]")):
            (self.repo / "source with spaces.lean").write_text(f"/-! {tag} -/\n")
            result = self.run_check()
            self.assertEqual(result["status"], "rejected", result)
            self.assertNotEqual(result["trace"]["candidate"]["status"], "passed")

    def test_ignored_lean_tags_are_diagnosed_even_in_block_comments(self):
        path = self.lean_source(f'def example := "{FAKE}"\n/-! {TAG} -/\n')
        snap = SimpleNamespace(root=self.repo, manifest=[{"path": path.name}])
        # [utest->req~ib-lean-annotations~1]
        self.assertEqual(annotation_diagnostics(snap, ["."], []), [f"{path.name}:2"])
        imported = [{"path": path.name, "line": 2, "type": "impl"}]
        self.assertEqual(annotation_diagnostics(snap, ["."], imported), [])
        with patch("intentbond.oft.import_items", return_value=[]):
            result = self.run_check()
        self.assert_problem(result, "OFT ignored standalone coverage comments")
        self.assertEqual(result["tests"]["status"], "not_run")

    def test_proof_tag_and_removing_sole_lean_implementation_are_checked(self):
        self.replace("requirements.md", "Needs: impl, utest", "Needs: impl, proof, utest")
        self.replace("session.py", "# " + TAG, "# Implementation is linked from Lean.")
        path = self.lean_source(f"-- {TAG}\n/-! [proof->req~session-expiration~1] -/\n")
        result = self.run_check()
        # [utest->req~ib-lean-annotations~1]
        self.assertEqual(result["status"], "passed", result)
        items = import_items(self.out / "candidate-items.xml", self.repo)
        self.assertTrue(any(i["type"] == "proof" and i["path"] == path.name for i in items))
        path.write_text(path.read_text().replace(TAG, "Implementation tag removed"))
        result = self.run_check()
        self.assertEqual(result["status"], "rejected", result)
        self.assertNotEqual(result["trace"]["candidate"]["status"], "passed")

    def test_trace_exclusion_does_not_import_lean_alias(self):
        path = self.lean_source(f"/-! {FAKE} -/\n")
        self.configure(lambda scope: scope.update(trace_exclude=[path.name]))
        # [utest->req~ib-lean-annotations~1]
        result = self.run_check()
        self.assertEqual(result["status"], "passed", result)
        items = import_items(self.out / "candidate-items.xml", self.repo)
        self.assertFalse(any(Path(i["path"]).suffix == ".lean" for i in items))

    def test_named_tags_and_multiple_links_on_one_line_keep_oft_semantics(self):
        self.lean_source("/- [impl~lean-session~1->req~session-expiration~1] -/\n")
        result = self.run_check()
        # [utest->req~ib-lean-annotations~1]
        self.assertEqual(result["status"], "passed", result)
        items = import_items(self.out / "candidate-items.xml", self.repo)
        self.assertTrue(any(i["id"] == "impl~lean-session~1" for i in items))
        (self.repo / "source with spaces.lean").write_text(f"/- {TAG} {FAKE} -/\n")
        result = self.run_check()
        self.assertEqual(result["status"], "rejected", result)
