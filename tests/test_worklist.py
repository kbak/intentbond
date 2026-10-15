"""Frozen reviews resume only against matching source, policy and retained evidence."""

import json
import shutil
from unittest.mock import patch

from test_workflow import WorkflowFixture

from intentbond import worklist
from intentbond.common import CheckError, read_json, write_json


class WorklistTests(WorkflowFixture):
    def setUp(self):
        super().setUp()
        self.replace("requirements.md", "30 minutes", "30 minutes of inactivity")
        self.run_check()
        self.queue = self.root / "review"

    def start(self):
        return worklist.start(
            self.out / "evidence.json", self.queue, self.repo, self.jar, scope_path=self.scope
        )

    def test_restart_defer_reopen_and_complete_never_clear_review_gate(self):
        # [utest->req~ib-review-worklist~1]
        original = (self.out / "evidence.json").read_bytes()
        started = self.start()
        first = started["current"]["id"]
        self.assertEqual(first, worklist.status(self.queue)["current"]["id"])
        result = worklist.record(self.queue, first, "deferred", "Need assertion review")
        self.assertEqual(result["counts"]["deferred"], 1)
        self.assertNotEqual(result["current"]["id"], first)
        # Resume from disk without OFT or tests; current source is still checked.
        with (
            patch("intentbond.explain.run", side_effect=AssertionError("no tracing")),
            patch("intentbond.runner.execute_tests", side_effect=AssertionError("no tests")),
        ):
            resumed = worklist.status(self.queue)
            self.assertEqual(resumed["counts"], result["counts"])
            for task in resumed["items"]:
                if task["state"] == "pending":
                    worklist.record(
                        self.queue, task["id"], "reviewed", "Inspected declarations and assertions"
                    )
            deferred = worklist.status(self.queue)
            self.assertIsNone(deferred["current"])
            self.assertEqual(deferred["status"], "incomplete")
            worklist.record(self.queue, first, "pending", "Reopened")
            self.assertEqual(worklist.status(self.queue)["current"]["id"], first)
            result = worklist.record(self.queue, first, "reviewed", "Checked boundary assertions")
        self.assertEqual(result["status"], "reviewed")
        self.assertEqual(result["recorded_review"]["status"], "required")
        self.assertEqual(result["recorded_check_status"], "review_required")
        history = next(item for item in result["items"] if item["id"] == first)["history"]
        self.assertEqual([entry["state"] for entry in history], ["deferred", "pending", "reviewed"])
        self.assertEqual(history[0]["message"], "Need assertion review")
        self.assertEqual((self.out / "evidence.json").read_bytes(), original)

    def test_source_mutation_requires_fresh_evidence_and_fresh_queue(self):
        first = self.start()["current"]["id"]
        reviewed = worklist.record(self.queue, first, "reviewed", "Inspected the original source")
        self.assertEqual(reviewed["counts"]["reviewed"], 1)
        (self.repo / "new-file.txt").write_text("New captured source.\n")
        before = (self.queue / "progress.json").read_bytes()
        with self.assertRaisesRegex(CheckError, "fresh check"):
            worklist.status(self.queue)
        self.run_check()
        with self.assertRaisesRegex(CheckError, "different evidence"):
            worklist.status(self.queue, evidence_path=self.out / "evidence.json")
        fresh = worklist.start(
            self.out / "evidence.json",
            self.root / "fresh-review",
            self.repo,
            self.jar,
            scope_path=self.scope,
        )
        self.assertEqual(fresh["counts"]["reviewed"], 0)
        self.assertTrue(any(item["id"] == "file:new-file.txt" for item in fresh["items"]))
        self.assertEqual((self.queue / "progress.json").read_bytes(), before)

    def test_changed_scope_or_evidence_rejected_without_progress_update(self):
        first = self.start()["current"]["id"]
        before = (self.queue / "progress.json").read_bytes()
        value = read_json(self.scope)
        value["review_paths"] = ["session.py"]
        write_json(self.scope, value)
        with self.assertRaisesRegex(CheckError, "scope differs"):
            worklist.record(self.queue, first, "reviewed", "Inspected")
        shutil.copyfile(self.repo / "scope.json", self.scope)
        path = self.out / "review.json"
        path.write_text(path.read_text() + " ")
        with self.assertRaisesRegex(CheckError, "artifact missing or changed"):
            worklist.status(self.queue)
        self.assertEqual((self.queue / "progress.json").read_bytes(), before)

    def test_progress_cannot_omit_duplicate_or_reorder_tasks(self):
        self.start()
        path = self.queue / "progress.json"
        original = read_json(path)
        for items in (
            original["items"][:-1],
            original["items"] + [original["items"][0]],
            original["items"][::-1],
        ):
            write_json(path, {**original, "items": items})
            with self.assertRaisesRegex(CheckError, "omits, duplicates or reorders"):
                worklist.status(self.queue)

    def test_relocated_bundle_and_checkout_preserve_context_and_notes(self):
        first = self.start()["current"]["id"]
        worklist.record(self.queue, first, "reviewed", "Checked relevant assertions")
        relocated_bundle = self.root / "relocated evidence"
        relocated_repo = self.root / "relocated repository"
        shutil.move(self.out, relocated_bundle)
        shutil.move(self.repo, relocated_repo)
        result = worklist.status(
            self.queue, evidence_path=relocated_bundle / "evidence.json", repo=relocated_repo
        )
        self.assertEqual(result["counts"]["reviewed"], 1)
        self.assertEqual(result["items"][0]["message"], "Checked relevant assertions")

    def test_cli_exposes_incomplete_status_and_current_context(self):
        code, output, error = self.run_cli(
            "review",
            "start",
            "--repo",
            str(self.repo),
            "--scope",
            str(self.scope),
            "--evidence",
            str(self.out / "evidence.json"),
            "--out",
            str(self.queue),
            "--format",
            "json",
        )
        self.assertEqual(code, 0, error)
        first = json.loads(output)["current"]["id"]
        code, output, error = self.run_cli("review", "next", "--worklist", str(self.queue))
        self.assertEqual(code, 4, error)
        self.assertIn(first, output)
        code, output, error = self.run_cli(
            "review",
            "record",
            first,
            "--worklist",
            str(self.queue),
            "--state",
            "reviewed",
            "-m",
            "Inspected",
        )
        self.assertEqual(code, 0, error)
        code, output, error = self.run_cli(
            "review", "status", "--worklist", str(self.queue), "--format", "json"
        )
        self.assertEqual(code, 4, error)
        self.assertEqual(json.loads(output)["counts"]["reviewed"], 1)

    def test_invalid_notes_unknown_tasks_and_concurrent_writer_preserve_progress(self):
        first = self.start()["current"]["id"]
        path = self.queue / "progress.json"
        before = path.read_bytes()
        for identifier, state, note in (
            (first, "reviewed", " "),
            (first, "approved", "Inspected"),
            ("missing", "reviewed", "Inspected"),
        ):
            with self.assertRaises(CheckError):
                worklist.record(self.queue, identifier, state, note)
        lock = self.queue / ".writer.lock"
        lock.touch()
        with self.assertRaisesRegex(CheckError, "Another review writer"):
            worklist.record(self.queue, first, "reviewed", "Inspected")
        self.assertEqual(path.read_bytes(), before)
        self.assertTrue(lock.exists())

    def test_unannotated_and_deleted_files_and_neighbors_are_not_omitted(self):
        (self.repo / "new.py").write_text("VALUE = 1\n")
        (self.repo / "session.py").unlink()
        self.configure(lambda scope: scope.update(inputs=["."]))
        self.run_check()
        result = self.start()
        ids = {item["id"] for item in result["items"]}
        self.assertIn("file:new.py", ids)
        self.assertIn("file:session.py", ids)
        self.assertTrue(any(identifier.startswith("artifact:base:impl~") for identifier in ids))
        self.assertIn("artifact:candidate:req~session-expiration~1", ids)
        self.assertEqual(result["recorded_check_status"], "rejected")

    def test_output_inside_source_or_evidence_and_overwriting_are_rejected(self):
        for output in (self.repo / "queue", self.out / "queue"):
            with self.assertRaisesRegex(CheckError, "outside"):
                worklist.start(self.out / "evidence.json", output, self.repo, self.jar)
        self.start()
        with self.assertRaises(FileExistsError):
            self.start()
