"""Derived review observations over OFT's graph, never a second tracing engine."""

from .common import within
from .execution import explain_execution


# [impl->req~ib-review-observations~1]
def graph_degrees(graph):
    """Count exact resolving edges, independent of OFT's stale reverse-link diagnostics."""
    incoming = {ref: set() for ref in graph}
    outgoing = {ref: set() for ref in graph}
    for target, item in graph.items():
        if not item.get("path"):
            continue
        for relation in item.get("covering_statuses", []):
            ref = relation["id"]
            if relation["status"] == "COVERING" and graph.get(ref, {}).get("path"):
                outgoing[ref].add(target)
                incoming[target].add(ref)
    return {
        ref: {
            "incoming": sorted(incoming[ref]),
            "outgoing": sorted(outgoing[ref]),
            "in": len(incoming[ref]),
            "out": len(outgoing[ref]),
        }
        for ref in graph
    }


def degree_lines(value):
    return [
        f"Immediate resolved links: in={value['in']}, out={value['out']} (review context, not an error)"
    ]


# [impl->req~ib-review-observations~1]
def inspect_graph(graph, scope, tests, links):
    artifacts = []
    degrees = graph_degrees(graph)
    for identifier, item in sorted(graph.items()):
        status, linked, diagnostics = explain_execution(identifier, graph, links, tests)
        artifacts.append(
            {
                **item,
                "degree": degrees[identifier],
                "linked_test_execution": status,
                "linked_tests": linked,
                "execution_link_diagnostics": diagnostics,
            }
        )
    required = set(scope["tests"].get("execution_links", {}).get("required_artifacts", []))
    execution = []
    for key in sorted(required):
        matches = [
            item
            for item in (links or {}).get("artifacts", [])
            if item["id"].rsplit("~", 1)[0] == key
        ]
        established = (
            tests.get("source_status") == "matched"
            and tests.get("exit_code") is not None
            and tests.get("status") != "error"
            and (links or {}).get("status") == "recorded"
        )
        status = matches[0]["status"] if len(matches) == 1 and established else "not_established"
        if status != "passed":
            execution.append({"key": key, "status": status, "observations": matches})
    hubs = sorted(
        [item for item in artifacts if max(item["degree"]["in"], item["degree"]["out"]) > 1],
        key=lambda item: (-max(item["degree"]["in"], item["degree"]["out"]), item["id"]),
    )
    return {
        "artifacts": artifacts,
        "coverage_gaps": [
            {
                "id": item["id"],
                "path": item["path"],
                "line": item["line"],
                "oft_status": item["oft_status"],
                "coverage": item["coverage"],
            }
            for item in artifacts
            if item["coverage"]["uncovered_types"] or item["coverage"]["deep"] == "UNCOVERED"
        ],
        "required_execution_gaps": execution,
        "hubs": [
            {"id": item["id"], "path": item["path"], "line": item["line"], **item["degree"]}
            for item in hubs
        ],
    }


# [impl->req~ib-review-observations~1]
def inspect_changes(before, after, inventory, scope):
    result = []
    for change in inventory["paths"]:
        path = change["path"]
        old = sorted(item["id"] for item in before.values() if item["path"] == path)
        new = sorted(item["id"] for item in after.values() if item["path"] == path)
        excluded = within(path, scope.get("trace_exclude", []))
        result.append(
            {
                **change,
                "base_artifacts": old,
                "candidate_artifacts": new,
                "annotation_status": "excluded_from_tracing"
                if excluded
                else "outside_tracing_inputs"
                if not change["tracing_input"]
                else "imported_artifacts"
                if new
                else "removed_file"
                if change["change"] == "deleted"
                else "no_imported_artifacts",
            }
        )
    return result


def render_inspection(value):
    lines = ["Review observations (declared relationships; no completeness or correctness score):"]
    for item in value.get("changed_files", []):
        lines.append(f"  {item['path']}: {item['annotation_status']}")
        lines.extend(f"    {ref}" for ref in item["candidate_artifacts"])
        lines.extend(
            f"    baseline: {ref}"
            for ref in item["base_artifacts"]
            if ref not in item["candidate_artifacts"]
        )
    for item in value["coverage_gaps"]:
        lines.append(
            f"  OFT coverage: {item['id']} deep={item['coverage']['deep']}, uncovered types={', '.join(item['coverage']['uncovered_types']) or '(none)'}; item status={item['oft_status']}"
        )
    for item in value["required_execution_gaps"]:
        lines.append(f"  Required execution: {item['key']} {item['status']}")
    for item in value["artifacts"]:
        if item["linked_tests"]:
            lines.append(f"  Linked execution: {item['id']} {item['linked_test_execution']}")
    for item in value["hubs"][:10]:
        lines.append(
            f"  Hub: {item['id']} in={item['in']}, out={item['out']} ({item['path']}:{item['line']})"
        )
        lines.append(f"    covers: {', '.join(item['outgoing']) or '(none)'}")
        lines.append(f"    covered by: {', '.join(item['incoming']) or '(none)'}")
    if len(value["hubs"]) > 10:
        lines.append(f"  {len(value['hubs']) - 10} more hubs in JSON")
    lines.append(
        "No imported artifacts does not establish missing requirements; hubs are inspection priorities, not errors."
    )
    return lines
