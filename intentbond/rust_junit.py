"""Common report and source-local binding conventions for the Rust producers."""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .common import CheckError, relative_path

TAG = r"[A-Za-z]+~[A-Za-z0-9][A-Za-z0-9_.-]*~[0-9]+"
BINDING = re.compile(rf"\s*//\s*\[({TAG})->{TAG}\]\s+ib-(cargo|verus)\s+(.+?)\s*")


def candidate_file(name):
    path = Path(relative_path(name))
    if not path.resolve().is_relative_to(Path.cwd().resolve()):
        raise CheckError(f"Path outside the candidate: {name}")
    return path


def fresh_output(name):
    path = candidate_file(name)
    if path.exists() or path.is_symlink():
        raise CheckError(f"Output already exists: {name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def bindings(paths, producer):
    """Only the explicit runner identity on the named declaration supplies a link."""
    result = {}
    for name in paths:
        for number, line in enumerate(
            candidate_file(name).read_text(encoding="utf-8").splitlines(), 1
        ):
            match = BINDING.fullmatch(line)
            if not match or match[2] != producer:
                continue
            identity = tuple(match[3].split(maxsplit=1)) if producer == "cargo" else match[3]
            if (producer == "cargo" and len(identity) != 2) or identity in result:
                raise CheckError(
                    f"{name}:{number}: invalid or duplicate {producer} binding {identity!r}"
                )
            result[identity] = match[1]
    return result


def property_value(element, name, value):
    properties = element.find("properties")
    if properties is None:
        properties = ET.SubElement(element, "properties")
    ET.SubElement(properties, "property", name=name, value=value)


def command_property(element, command):
    property_value(element, "command", json.dumps(command, ensure_ascii=True))


def write_report(path, suite):
    with path.open("xb") as stream:
        ET.ElementTree(suite).write(stream, encoding="utf-8", xml_declaration=True)
