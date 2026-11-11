"""Body-comment regressions with exact protected-byte and rejection controls."""

import unittest

from repair_boundary_fixture import BEFORE, PROPOSED

from intentbond.repair import outside_symbol


class CommentBoundaryTests(unittest.TestCase):
    def test_recorded_reservation_proposal_is_a_permitted_body_edit(self):
        # [utest->req~ib-repair-boundaries~1]
        self.assertEqual(
            outside_symbol(BEFORE, "Service.batch"), outside_symbol(PROPOSED, "Service.batch")
        )

    def test_comments_and_blank_lines_in_function_and_method_bodies(self):
        # [utest->req~ib-repair-boundaries~1]
        headers = (
            "def work(x='é'):\n",
            "async def work(x='é'):\n",
            "@decorate('漢')\ndef work(x='é'):\n",
            "def work(\n    x: dict[str, str] = {'漢': ':'},\n) -> str:  # header\n",
            "@decorate('漢')\nasync def work(\n    x='é',\n):\n",
        )
        for header in headers:
            for method in (False, True):
                for newline in ("\n", "\r\n", "\r"):
                    with self.subTest(header=header, method=method, newline=newline):
                        prefix = "# protected é\n" + header
                        body = "    return x\n"
                        changed = (
                            "\n    # reason 漢\n\n    return str(x)  # result\n"
                            "\n    # still in this body\n"
                        )
                        suffix = "\n# protected separator\ndef other():\n    return 7\n"
                        if method:
                            prefix = "class Store:\n" + "".join(
                                "    " + line for line in prefix.splitlines(keepends=True)
                            )
                            body = "    " + body
                            changed = "".join(
                                "    " + line if line.strip() else line
                                for line in changed.splitlines(keepends=True)
                            )
                        old, new = (
                            (prefix + middle + suffix).replace("\n", newline)
                            for middle in (body, changed)
                        )
                        symbol = "Store.work" if method else "work"
                        expected = (
                            (prefix + "<repair-body>" + "\n" + suffix)
                            .replace("\n", newline)
                            .encode()
                        )
                        self.assertEqual(outside_symbol(old, symbol), expected)
                        self.assertEqual(outside_symbol(new, symbol), expected)

    def test_inline_unicode_and_tab_indentation(self):
        # [utest->req~ib-repair-boundaries~1]
        pairs = (
            ("def work(x='é'): ", "return x", "return '漢'  # comment", "\n"),
            ("def work(\n x='é'): ", "return x", "return '漢'  # comment", "\n"),
            ("def work():\n", "\treturn 1", "\t# reason\n\treturn 2", "\n"),
            ("def work():\n", "    return 1", "    # reason\n    return 2", ""),
        )
        for prefix, old, new, suffix in pairs:
            with self.subTest(prefix=prefix, suffix=suffix):
                self.assertEqual(
                    outside_symbol(prefix + old + suffix, "work"),
                    outside_symbol(prefix + new + suffix, "work"),
                )

    def test_first_statement_decorators_belong_to_the_selected_outer_body(self):
        # [utest->req~ib-repair-boundaries~1]
        old = "def work():\n    @decorate('é')\n    def inner():\n        return 1\n"
        new = "def work():\n    # reason\n    @other\n    def inner():\n        return 2\n"
        self.assertEqual(outside_symbol(old, "work"), outside_symbol(new, "work"))
        self.assertNotEqual(outside_symbol(old, "work.inner"), outside_symbol(new, "work.inner"))

    def test_signatures_decorators_and_outside_comments_remain_protected(self):
        # [utest->req~ib-repair-boundaries~1]
        old = (
            "# module\n@decorate('é')\nasync def work(\n"
            "    x='漢',  # parameter\n):  # header\n"
            "    # body\n    return x\n"
            "# outside\n    # beyond the outside separator\n"
            "\ndef other():\n    return 7\n"
        )
        for before, after in (
            ("# module", "# changed"),
            ("@decorate('é')", "@decorate('漢')"),
            ("async def", "def"),
            ("x='漢'", "x='é'"),
            ("# parameter", "# changed"),
            ("# header", "# changed"),
            ("# outside", "# changed"),
            ("# beyond the outside separator", "# changed"),
            ("return 7", "return 8"),
        ):
            with self.subTest(before=before):
                self.assertNotEqual(
                    outside_symbol(old, "work"),
                    outside_symbol(old.replace(before, after), "work"),
                )
        # Comments at the enclosing indentation do not become writable merely
        # because Python ignores them before the first statement of a suite.
        old = "def work():\n# outside\n    # body\n    return 1\n"
        self.assertNotEqual(
            outside_symbol(old, "work"),
            outside_symbol(old.replace("# outside", "# changed"), "work"),
        )


if __name__ == "__main__":
    unittest.main()
