"""A physical-line-preserving comment view for Lean's core lexical forms.

This is an import adapter, not a Lean parser or proof checker. OFT still parses
the tags. Source snapshots and the program run by the caller are never rewritten.
"""

import re

from .common import CheckError


# [impl->req~ib-lean-annotations~1]
def comment_lines(content, path):
    """Return UTF-8 comment text for OFT and the original comment line numbers."""
    try:
        source = content.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeError as exc:
        raise CheckError(f"Cannot read Lean annotations in {path}: {exc}") from exc
    view = ["\n" if c == "\n" else " " for c in source]

    def fail(kind, start):
        line = source.count("\n", 0, start) + 1
        raise CheckError(f"Cannot read Lean annotations in {path}:{line}: unterminated {kind}")

    def block(start):
        i, depth = start + 2, 1
        while i < len(source):
            if source.startswith("/-", i):
                depth += 1
                i += 2
            elif source.startswith("-/", i):
                depth -= 1
                i += 2
                if not depth:
                    return i
            else:
                view[i] = source[i]
                i += 1
        fail("block comment", start)

    def string(start, interpolated=False):
        i = start + 1
        while i < len(source):
            if source[i] == "\\":
                i += 2
            elif source[i] == '"':
                return i + 1
            elif interpolated and source[i] == "{":
                i = code(i + 1, closing=True)
            else:
                i += 1
        fail("string", start)

    def character(start):
        i = start + 1
        if source[i : i + 1] == "\\":
            i += 1
            escape = source[i : i + 1]
            i += {"x": 3, "u": 5}.get(escape, 1)
        else:
            i += 1
        if source[i : i + 1] != "'":
            fail("character literal", start)
        return i + 1

    def code(i, closing=False):
        start, depth = i, 0
        interpolation = False
        while i < len(source):
            if source[i].isspace():
                i += 1
            elif source.startswith("--", i):
                end = source.find("\n", i)
                end = len(source) if end < 0 else end
                view[i + 2 : end] = source[i + 2 : end]
                i = end
            elif source.startswith("/-", i):
                i = block(i)
            elif source[i] == "«":
                end = source.find("»", i + 1)
                if end < 0:
                    fail("escaped identifier", i)
                i = end + 1
                interpolation = False
            elif source[i] == "r" and (raw := re.match(r'r(#+|)"', source[i:])):
                end = source.find('"' + raw[1], i + len(raw[0]))
                if end < 0:
                    fail("raw string", i)
                i = end + 1 + len(raw[1])
                interpolation = False
            elif source[i] == '"':
                i = string(i, interpolated=interpolation)
                interpolation = False
            elif source.startswith("''", i):
                i += 2
                interpolation = False
            elif source.startswith("'(", i) and i > 0 and source[i - 1] == "]":
                # Explicit getElem proof: xs[i]'(by omega).
                i += 1
                interpolation = False
            elif source[i] == "'":
                i = character(i)
                interpolation = False
            elif source[i].isalpha() or source[i] == "_":
                end = i + 1
                while end < len(source) and (source[end].isalnum() or source[end] in "_'!?"):
                    end += 1
                interpolation = source[i:end] in {"s!", "m!", "f!"}
                i = end
            elif closing and source[i] == "{":
                depth += 1
                i += 1
                interpolation = False
            elif closing and source[i] == "}":
                if depth == 0:
                    return i + 1
                depth -= 1
                i += 1
                interpolation = False
            else:
                i += 1
                interpolation = False
        if closing:
            fail("string interpolation", start)
        return i

    code(0)
    lines = "".join(view).split("\n")
    comments = {i for i, line in enumerate(lines, 1) if line.strip()}
    # Every line becomes a comment in a supported OFT input format. Only physical
    # line numbers, not columns, form part of the retained OFT source location.
    return "\n".join("// " + line if line.strip() else "" for line in lines).encode(), comments
