"""Source identity and selected review remain separate, reproducible results."""

from test_workflow import WorkflowFixture

from intentbond.check_output import render_check
from intentbond.common import CheckError, digest, read_json, write_json
from intentbond.config import load_baseline_scope, validate_scope
from intentbond.evidence import statement
from intentbond.explain import explain, render_explanation
from intentbond.review import changes, review_selection
from intentbond.runner import verify
from intentbond.snapshot import snapshot


class BoundaryTests(WorkflowFixture):
    # [utest->req~ib-review-selection~1]
    def test_review_globs_bind_both_sides_of_moves_to_the_baseline(self):
        policy = self.repo / ".intentbond/scope.json"
        scope = read_json(policy)
        scope.update(review_paths=["literal/*.toml"], review_globs=["**/*.rs"])
        write_json(policy, scope)

        def create(name):
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name)

        for name in ("old.rs", "into.txt", "out.rs", "from.rs"):
            create(name)
        self.commit()
        base = self.git("rev-parse", "HEAD").strip()
        create("notes.md")
        code, stdout, _ = self.run_cli("check", "--base", base)
        self.assertEqual(code, 0, stdout)

        added = [
            "build.rs",
            "tests/root.rs",
            "examples/example.rs",
            "benches/bench.rs",
            ".x/a/b/c.rs",
        ]
        for name in added:
            create(name)
        (self.repo / "old.rs").unlink()
        for old, new in (("into.txt", "into.rs"), ("out.rs", "out.txt"), ("from.rs", "to.rs")):
            (self.repo / old).rename(self.repo / new)
        scope.pop("review_globs")
        write_json(policy, scope)
        self.commit()
        head = self.git("rev-parse", "HEAD").strip()
        out = self.root / "review-evidence"
        code, stdout, _ = self.run_cli(
            "check", "--base", base, "--candidate", head, "--out", str(out)
        )
        self.assertEqual(code, 4, stdout)
        before = snapshot(self.repo, base, self.root / "before")
        after = snapshot(self.repo, head, self.root / "after")
        selected = changes(before, after, [], [], load_baseline_scope(self.repo, base))
        review = read_json(out / "review.json")
        self.assertEqual(review["changes"], selected)
        self.assertEqual(review["base_commit"], base)
        self.assertEqual(review["base_sha256"], before.sha256)
        self.assertEqual(review["candidate_sha256"], after.sha256)
        self.assertEqual(read_json(out / "evidence.json")["predicate"]["candidate"]["commit"], head)
        self.assertEqual(
            {c["path"] for c in selected},
            set(added) | {"old.rs", "into.rs", "out.rs", "from.rs", "to.rs"},
        )
        boundaries = {p["path"]: p for p in review["source_boundaries"]["paths"]}
        self.assertEqual(boundaries["out.rs"]["change"], "deleted")
        self.assertEqual(boundaries["into.rs"]["change"], "added")
        self.assertEqual(boundaries["tests/root.rs"]["semantic_review_selection"], "test")
        self.assertIsNone(boundaries["out.txt"]["semantic_review_selection"])
        self.assertEqual(
            verify(self.repo, None, base, head, out / "evidence.json", allow_pending_review=True)[
                "review"
            ],
            "required",
        )

    def test_anchored_glob_grammar_and_literal_root_compatibility(self):
        original = read_json(self.scope)
        for globs in (
            [],
            ["."],
            ["../*.rs"],
            ["/a"],
            ["a//b"],
            ["./a"],
            [".git/**"],
            ["a**b"],
            ["a["],
            ["a\\b"],
            ["a\x00b"],
            ["a", "a"],
            "*",
            [False],
        ):
            with self.subTest(globs=globs), self.assertRaises(CheckError):
                validate_scope({**original, "review_globs": globs})
        scope = validate_scope(
            {
                **original,
                "review_paths": ["literal/*.rs"],
                "review_globs": ["lib/**/case?.rs", "*.toml"],
            }
        )
        for name in ("lib/case1.rs", "lib/a/b/case_.rs", "x.toml", "literal/*.rs/child"):
            self.assertEqual(review_selection(name, scope), "review", name)
        for name in (
            "x/lib/case1.rs",
            "lib/case12.rs",
            "lib/a/case1.RS",
            "x/t.toml",
            "literal/test.rs",
        ):
            self.assertIsNone(review_selection(name, scope), name)

    def test_review_only_fixtures_trigger_bound_review_without_importing_examples(self):
        path = self.repo / "fixtures/example.md"
        path.parent.mkdir()
        path.write_text("# Example\n\n`req~illustrative~1`\n\nNeeds: impl\n")
        self.configure(lambda scope: scope.update(review_paths=["fixtures"]))
        result = self.run_check()
        # [utest->req~ib-change-review~1]
        # [utest->req~ib-review-selection~1]
        self.assertEqual(result["status"], "review_required", result)
        self.assertEqual(result["review"]["change_count"], 1)
        self.assertNotIn("illustrative", (self.out / "candidate-items.xml").read_text())
        self.assertEqual(
            result["source_boundaries"]["paths"],
            [
                {
                    "path": "fixtures/example.md",
                    "change": "added",
                    "tracing_input": False,
                    "semantic_review_selection": "review",
                }
            ],
        )
        verify(
            self.repo,
            self.scope,
            self.base,
            "worktree",
            self.out / "evidence.json",
            allow_pending_review=True,
        )
        self.configure(lambda scope: scope.pop("review_paths"))
        with self.assertRaises(CheckError):
            verify(
                self.repo,
                self.scope,
                self.base,
                "worktree",
                self.out / "evidence.json",
                allow_pending_review=True,
            )

    def test_review_paths_use_existing_literal_path_validation(self):
        original = read_json(self.scope)
        for paths in (
            [],
            "fixtures",
            ["../fixtures"],
            [".git"],
            ["/tmp"],
            ["fixtures", "fixtures"],
        ):
            # [utest->req~ib-review-selection~1]
            with self.subTest(paths=paths), self.assertRaises(CheckError):
                validate_scope({**original, "review_paths": paths})
        self.assertEqual(
            validate_scope({**original, "review_paths": ["fixtures"]})["review_paths"], ["fixtures"]
        )

    def test_outside_docs_are_counted_hashed_and_reject_stale_evidence(self):
        (self.repo / "notes").mkdir()
        path = self.repo / "notes/assessment.md"
        path.write_text("An assessment requiring ordinary review.\n")
        result = self.run_check()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["review"]["change_count"], 0)
        boundaries = result["source_boundaries"]
        # [utest->req~ib-boundary-report~1]
        self.assertEqual(
            boundaries["counts"],
            {
                "all_changed_captured_source_paths": 1,
                "changed_tracing_input_paths": 0,
                "changed_selected_semantic_review_paths": 0,
                "changed_paths_outside_selected_semantic_review": 1,
            },
        )
        self.assertEqual(boundaries["paths"][0]["path"], "notes/assessment.md")
        self.assertNotEqual(result["base"]["sha256"], result["candidate"]["sha256"])
        self.assertEqual(read_json(self.out / "review.json")["source_boundaries"], boundaries)
        rendered = render_check(result, self.out)
        self.assertIn("Changed captured source paths: 1", rendered)
        self.assertIn("neither approval nor rejection", rendered)
        explained = explain("req~session-expiration~1", self.out / "evidence.json", self.jar)
        self.assertEqual(explained["source_boundaries"], boundaries)
        self.assertIn("outside selected semantic review: 1", render_explanation(explained))
        self.assertIn("still source-hashed", (self.out / "summary.md").read_text())
        path.write_text("Edited after check.\n")
        with self.assertRaisesRegex(CheckError, "Candidate contents differ"):
            verify(self.repo, self.scope, self.base, "worktree", self.out / "evidence.json")

    def test_implementation_only_change_is_traced_but_not_selected_spec_test_review(self):
        with (self.repo / "session.py").open("a") as handle:
            handle.write("\n# Behavior is unchanged.\n")
        result = self.run_check()
        self.assertEqual(result["status"], "passed")
        counts = result["source_boundaries"]["counts"]
        self.assertEqual(counts["all_changed_captured_source_paths"], 1)
        self.assertEqual(counts["changed_tracing_input_paths"], 1)
        self.assertEqual(counts["changed_selected_semantic_review_paths"], 0)
        self.assertEqual(result["source_boundaries"]["paths"][0]["path"], "session.py")

    def test_implementation_review_selection_is_adopted_from_baseline(self):
        # [utest->req~ib-review-selection~1]
        scope = read_json(self.repo / ".intentbond/scope.json")
        scope["review_paths"] = ["session.py"]
        write_json(self.repo / ".intentbond/scope.json", scope)
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()
        with (self.repo / "session.py").open("a") as handle:
            handle.write("\n# Implementation edit remains reviewable.\n")
        scope.pop("review_paths")
        write_json(self.repo / ".intentbond/scope.json", scope)
        result = self.run_check(scope_path=None)
        self.assertEqual(result["status"], "review_required")
        change = next(
            item for item in result["source_boundaries"]["paths"] if item["path"] == "session.py"
        )
        self.assertEqual(change["semantic_review_selection"], "review")

    def test_requirement_changes_keep_pending_review_and_distinct_file_counts(self):
        for path in ("requirements.md", "session.py", "tests/test_session.py"):
            self.replace(path, "req~session-expiration~1", "req~session-expiration~2")
        result = self.run_check()
        self.assertEqual(result["status"], "review_required")
        counts = result["source_boundaries"]["counts"]
        self.assertEqual(counts["all_changed_captured_source_paths"], 3)
        self.assertEqual(counts["changed_selected_semantic_review_paths"], 2)
        self.assertGreater(
            result["review"]["change_count"], counts["changed_selected_semantic_review_paths"]
        )
        with self.assertRaises(CheckError):
            verify(self.repo, self.scope, self.base, "worktree", self.out / "evidence.json")
        verify(
            self.repo,
            self.scope,
            self.base,
            "worktree",
            self.out / "evidence.json",
            allow_pending_review=True,
        )

    def test_inventory_is_recomputed_and_legacy_evidence_remains_readable(self):
        with (self.repo / "session.py").open("a") as handle:
            handle.write("\n# Changed source.\n")
        result = self.run_check()
        review = read_json(self.out / "review.json")
        result["source_boundaries"]["counts"]["all_changed_captured_source_paths"] = 0
        review["source_boundaries"] = result["source_boundaries"]
        write_json(self.out / "review.json", review)
        result["artifacts"]["review.json"] = digest((self.out / "review.json").read_bytes())
        write_json(self.out / "evidence.json", statement(result))
        with self.assertRaisesRegex(CheckError, "boundary inventory"):
            verify(self.repo, self.scope, self.base, "worktree", self.out / "evidence.json")
        del result["source_boundaries"]
        del review["source_boundaries"]
        write_json(self.out / "review.json", review)
        result["artifacts"]["review.json"] = digest((self.out / "review.json").read_bytes())
        write_json(self.out / "evidence.json", statement(result))
        original = (self.out / "evidence.json").read_bytes()
        verify(self.repo, self.scope, self.base, "worktree", self.out / "evidence.json")
        explained = explain("req~session-expiration~1", self.out / "evidence.json", self.jar)
        self.assertEqual(
            explained["source_boundaries"]["counts"]["all_changed_captured_source_paths"], 1
        )
        self.assertEqual((self.out / "evidence.json").read_bytes(), original)
