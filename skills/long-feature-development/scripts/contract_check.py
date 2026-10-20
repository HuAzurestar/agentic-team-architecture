#!/usr/bin/env python3
"""Read-only checks and table rendering for Feature Markdown/YAML records.

Requires PyYAML. Does not authenticate authority, evaluate business policy,
contact services, write state, or require Git.
"""

from __future__ import annotations

import argparse
from html import escape
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

sys.dont_write_bytecode = True

import project_refs
from index_blocks import fenced_at, region_bounds

try:
    import yaml
except ImportError:
    yaml = None


class ContractError(ValueError):
    """A Feature record or its table is inconsistent."""


if yaml is not None:
    class DetailLoader(yaml.SafeLoader):
        pass

    # Preserve timestamps as source strings for deterministic table rendering.
    DetailLoader.yaml_implicit_resolvers = {
        key: [(tag, pattern) for tag, pattern in values
              if tag != "tag:yaml.org,2002:timestamp"]
        for key, values in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }

    def unique_mapping(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise ContractError("YAML metadata keys must be strings")
            if key in result:
                raise ContractError(f"duplicate YAML key: {key}")
            result[key] = loader.construct_object(value_node, deep=deep)
        return result

    DetailLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
    )


DESIGN_TYPES = {"requirement", "solution", "intent"}
DESIGN_COLUMNS = ["id", "title", "type", "state", "decided by", "decided at", "decided with"]
TASK_COLUMNS = ["id", "type", "title", "state", "owner", "depends on", "started at", "completed at", "head sha"]
DETAIL_SPEC_MAX_CHARS = 50
DETAIL_SPEC_MAX_LINES = 3
RELATIONS = {"requirement related to": "requirement", "solution related to": "solution", "intent related to": "intent"}
DESIGN_STATES = {"RECORDED", "PROPOSED", "REOPENED", "CONFIRMED",
                 "REJECTED", "OUT-OF-SCOPE", "INFEASIBLE"}
DECIDED_STATES = {"CONFIRMED", "REJECTED", "OUT-OF-SCOPE", "INFEASIBLE"}
TASK_STATES = {"PENDING", "WIP", "BLOCKED", "RECORDING", "DONE"}
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{label} must be a nonempty string")


def mapping(value, label):
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be a mapping")


def strings(value, label):
    if not isinstance(value, list):
        raise ContractError(f"{label} must be a list")
    for item in value:
        text(item, label)


def reference(value, label):
    mapping(value, label)
    for key in ("id", "revision", "location"):
        text(value.get(key), f"{label}.{key}")


def references(value, label):
    if not isinstance(value, list):
        raise ContractError(f"{label} must be a list")
    for item in value:
        reference(item, label)


def reject_transient_refs(value, label="record"):
    if isinstance(value, dict):
        for key, item in value.items():
            reject_transient_refs(item, f"{label}.{key}")
    elif isinstance(value, list):
        for item in value:
            reject_transient_refs(item, label)
    elif isinstance(value, str):
        whole = unquote(value).replace("\\", "/").split("#", 1)[0].split("?", 1)[0]
        if not any(c.isspace() for c in whole) and re.search(r"(?:^|[/：:])gists$", whole, re.IGNORECASE):
            raise ContractError(f"{label} cites disposable VERBAL/gists material")
        for token in re.split(r"[\s`\"'<>\[\]()]+", unquote(value)):
            location = token.replace("\\", "/").split("#", 1)[0].split("?", 1)[0]
            if re.search(r"(?:^|[/：:])gists/|(?:^|[/：:])VERBAL\.md(?:$|[.,;，。；])",
                         location, re.IGNORECASE):
                raise ContractError(f"{label} cites disposable VERBAL/gists material")


def body_headings(body):
    """Return real ATX/Setext heading spans, levels and titles outside fences."""
    headings = []
    for match in re.finditer(r"^ {0,3}(#{1,6})(?:[ \t]+([^\r\n]*))?\r?$",
                             body, re.MULTILINE):
        if not fenced_at(body, match.start()):
            title = re.sub(r"(?:^|[ \t]+)#+[ \t]*$", "", match[2] or "").strip()
            headings.append((match.start(), match.end(), len(match[1]), title))
    for match in re.finditer(r"^ {0,3}(\S[^\r\n]*)\r?\n {0,3}(=+|-+)[ \t]*\r?$",
                             body, re.MULTILINE):
        title = match[1].strip()
        if (fenced_at(body, match.start()) or fenced_at(body, match.start(2))
                or re.match(r"(?:#{1,6}(?:[ \t]|$)|>|[-+*][ \t]|\d+[.)][ \t]|[`~]{3})",
                            title)):
            continue
        # A Setext heading owns its whole paragraph, not just the last text line.
        start = match.start()
        while start:
            previous_end = start - 1
            previous_start = body.rfind("\n", 0, previous_end) + 1
            previous = body[previous_start:previous_end].rstrip("\r")
            if (not previous.strip()
                    or re.match(r"^(?: {4}|\t| {0,3}(?:#{1,6}(?:[ \t]|$)|>|<|"
                                r"[-+*][ \t]|\d+[.)][ \t]|[`~]{3}|[=-]+[ \t]*$))",
                                previous)):
                break
            start = previous_start
        title = " ".join(line.strip() for line in body[start:match.start(2)].splitlines()).strip()
        headings.append((start, match.end(), 1 if match[2][0] == "=" else 2, title))
    return sorted(headings)


def reject_transient_body_refs(body, record, label, domain=None):
    """Separate descriptive titles and original INT wording from formal citations."""
    headings = body_headings(body)
    displayed_titles = {record["title"], f"{record['id']} — {record['title']}"}
    literal_spans = [(left, right) for left, right, level, title in headings
                     if level == 1 and title in displayed_titles]
    if record_domain(record, domain) == "design" and record["type"].casefold() == "intent":
        for index, (_, right, level, title) in enumerate(headings):
            if title.casefold() not in ("original external wording", "\u5916\u90e8\u539f\u59cb\u8bf4\u660e"):
                continue
            end = next((following[0] for following in headings[index + 1:]
                        if following[2] <= level), len(body))
            literal_spans.append((right, end))
    checked = []
    position = 0
    for left, right in sorted(literal_spans):
        if left >= position:
            checked.extend((body[position:left], "\n"))
        position = max(position, right)
    checked.append(body[position:])
    reject_transient_refs("".join(checked), label)


def relation_items(value, label):
    items = value if isinstance(value, list) else [value]
    if value is None:
        return []
    for item in items:
        if isinstance(item, str):
            if not ID_RE.fullmatch(item):
                raise ContractError(f"{label} must contain record IDs or versioned references")
        else:
            reference(item, label)
    return items


def values(value, label):
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    for item in items:
        text(item, label)
    return items


def record_domain(record, domain=None):
    """Prefer explicit module context; extension fields must not reclassify tasks."""
    if domain is not None:
        return domain
    if record["type"].casefold() in DESIGN_TYPES:
        return "design"
    if "depends on" in record:
        return "tasks"
    if all(key in record for key in ("decided by", "decided at", "decided with")):
        return "design"
    return "tasks"


def validate(record, domain=None):
    mapping(record, "frontmatter")
    for key in ("id", "type", "title", "state"):
        text(record.get(key), key)
    if "revision" in record:
        text(record["revision"], "revision")
    if not ID_RE.fullmatch(record["id"]):
        raise ContractError("id must be a stable filename-safe identifier")
    record_type = record["type"].casefold()
    domain = record_domain(record, domain)
    is_design = domain == "design"
    if domain == "tasks" and record_type in DESIGN_TYPES:
        raise ContractError("design points belong in design/")
    # Titles describe the work; task gists are optional reference-only annotations.
    # Neither supplies evidence. Nested fields and all formal references stay checked.
    reject_transient_refs({k: v for k, v in record.items()
                           if k not in ("history", "title")
                           and not (not is_design and k == "gists")})
    references(record.get("inputs", []), "inputs")
    for label in RELATIONS:
        if label in record:
            relation_items(record[label], label)
    if is_design:
        if record["state"] not in DESIGN_STATES:
            raise ContractError("unknown design state")
        for key in ("decided by", "decided at", "decided with"):
            if key not in record:
                raise ContractError(f"design metadata requires {key}")
            if record[key] is not None:
                text(record[key], key)
        if record_type == "intent":
            # INT records who expressed it, not approval of its derived REQ/SOL.
            # Source time/reason may be unknown; never invent them to fill a tuple.
            text(record["decided by"], "intent.decided by (originator)")
        else:
            decided = [record[key] is not None for key in ("decided by", "decided at", "decided with")]
            if any(decided) and not all(decided):
                raise ContractError("decision metadata must be entirely set or entirely null")
            if record["state"] in DECIDED_STATES:
                for key in ("decided by", "decided at", "decided with"):
                    text(record[key], key)
    else:
        if record["state"] not in TASK_STATES:
            raise ContractError("unknown task lifecycle state")
        for key in ("owner", "depends on", "started at", "completed at", "head sha"):
            if key not in record:
                raise ContractError(f"task metadata requires {key}")
        strings(record["depends on"], "depends on")
        if len(record["depends on"]) != len(set(record["depends on"])):
            raise ContractError("duplicate task dependency")
        if record["owner"] is not None:
            text(record["owner"], "owner")
        if record["state"] != "PENDING":
            text(record["owner"], "owner")
        for key in ("started at", "completed at"):
            if record[key] is not None:
                text(record[key], key)
        for point in values(record["head sha"], "head sha"):
            project_refs.parse_ref(point, "point")
        for key in ("working branch", "integration branch"):
            for area in values(record.get(key), key):
                project_refs.parse_ref(area, "area")
        for project in values(record.get("project repository"), "project repository"):
            if not project_refs.KEY.fullmatch(project):
                raise ContractError("project repository must list stable project keys")
        if "gists" in record:
            strings(record["gists"], "gists (reference only)")
        if "resume action" in record:
            text(record["resume action"], "resume action")
        result = record.get("result")
        if result is not None:
            mapping(result, "result")
            text(result.get("execution"), "result.execution")
            references(result.get("evidence", []), "result.evidence")
            strings(result.get("remaining", []), "result.remaining")
            if record["state"] == "DONE":
                text(result.get("outcome"), "result.outcome")
                text(result.get("summary"), "result.summary")
            if result.get("outcome") == "pass" and not result.get("evidence"):
                raise ContractError("a passing result requires durable evidence")
        if record_type == "decision":
            decision = record.get("decision")
            mapping(decision, "decision")
            reference(decision.get("subject"), "decision.subject")
            if decision.get("conclusion") is not None or record["state"] == "DONE":
                for key in ("conclusion", "decider", "comment"):
                    text(decision.get(key), f"decision.{key}")
                reference(decision.get("authority ref"), "decision.authority ref")
                if decision.get("mode") not in ("direct", "delegated"):
                    raise ContractError("decision.mode must be direct or delegated")
                if decision["mode"] == "delegated":
                    text(decision.get("on behalf of"), "decision.on behalf of")
        if record_type == "feedback":
            feedback = record.get("feedback")
            mapping(feedback, "feedback")
            reference(feedback.get("subject"), "feedback.subject")
        if record_type == "gate":
            gate = record.get("gate")
            mapping(gate, "gate")
            evaluation, authorization = gate.get("evaluation"), gate.get("authorization")
            if evaluation not in ("satisfied", "unsatisfied", "unknown"):
                raise ContractError("unknown gate evaluation")
            if authorization not in ("granted", "denied", "pending", "not_required"):
                raise ContractError("unknown gate authorization")
            strings(gate.get("criteria"), "gate.criteria")
            strings(gate.get("allowed actions"), "gate.allowed actions")
            if evaluation != "unknown":
                reference(gate.get("subject"), "gate.subject")
                reference(gate.get("policy ref"), "gate.policy ref")
                if not gate["criteria"]:
                    raise ContractError("evaluated gate requires externally supplied criteria")
            if evaluation == "satisfied" and not (result or {}).get("evidence"):
                raise ContractError("satisfied gate requires durable evidence")
            if authorization == "granted":
                reference(gate.get("decision ref"), "gate.decision ref")
            if gate["allowed actions"] and (evaluation != "satisfied"
                    or authorization not in ("granted", "not_required")):
                raise ContractError("allowed actions require satisfied checks and applicable authorization")
    retained_versions(record, domain)
    return record


def retained_versions(record, domain=None):
    """Current metadata plus complete historical snapshots in this detail."""
    versions = {record["revision"]: record} if record.get("revision") else {}
    history = record.get("history", [])
    if not isinstance(history, list):
        raise ContractError("history must be a list of metadata/body snapshots")
    for entry in history:
        mapping(entry, "history entry")
        metadata = entry.get("metadata")
        mapping(metadata, "history.metadata")
        text(entry.get("body"), "history.body")
        if metadata.get("history"):
            raise ContractError("historical metadata must not nest history")
        validate(metadata, record_domain(record, domain))
        text(metadata.get("revision"), "history.metadata.revision")
        reject_transient_body_refs(entry["body"], metadata, "history.body",
                                   record_domain(record, domain))
        if metadata["id"] != record["id"] or metadata["type"].casefold() != record["type"].casefold():
            raise ContractError("historical snapshot identity/type mismatch")
        if metadata["revision"] in versions:
            raise ContractError("historical revisions must be unique and differ from current")
        versions[metadata["revision"]] = metadata
    return versions


def load(path, domain=None):
    if yaml is None:
        raise ContractError("PyYAML is required for YAML frontmatter checks")
    content = Path(path).read_text(encoding="utf-8-sig")
    match = re.match(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)",
                     content, re.DOTALL)
    if not match:
        raise ContractError(f"{path}: expected YAML frontmatter")
    try:
        record = yaml.load(match.group(1), Loader=DetailLoader)
    except yaml.YAMLError as exc:
        raise ContractError(f"{path}: invalid YAML: {exc}") from exc
    if domain is None and Path(path).parent.name in ("design", "tasks"):
        domain = Path(path).parent.name
    validate(record, domain)
    reject_transient_body_refs(content[match.end():], record, f"{path} body", domain)
    return record


def collect(root, project_root=None):
    groups = {"design": {}, "tasks": {}}
    all_ids = set()
    for domain, records in groups.items():
        directory = root / domain
        if not directory.is_dir():
            raise ContractError(f"missing {domain}/ directory")
        for path in sorted(directory.rglob("*.md")):
            record = load(path, domain)
            if path.parent != directory or path.stem != record["id"]:
                raise ContractError(f"{path}: expected {domain}/{record['id']}.md")
            if record["id"] in all_ids:
                raise ContractError(f"duplicate record ID: {record['id']}")
            all_ids.add(record["id"])
            records[record["id"]] = record
    tasks = groups["tasks"]
    visited = set()
    active = set()

    def visit(task_id):
        if task_id in active:
            raise ContractError("task dependencies contain a cycle")
        if task_id in visited:
            return
        active.add(task_id)
        for dependency in tasks[task_id]["depends on"]:
            if dependency not in tasks:
                raise ContractError(f"{task_id}: unknown task dependency {dependency}")
            visit(dependency)
        active.remove(task_id)
        visited.add(task_id)

    for task_id in tasks:
        visit(task_id)
    validate_local_refs(root, groups)
    if project_root is not None:
        validate_projects(groups, project_root)
    return groups


def validate_local_refs(root, groups):
    """Check references into this Feature; external locators remain unresolved."""
    versions = {
        record["id"]: retained_versions(record, domain)
        for domain, records in groups.items() for record in records.values()
    }
    def visit(value):
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            if all(key in value for key in ("id", "revision", "location")):
                reference(value, "versioned reference")
                location = unquote(value["location"]).replace("\\", "/")
                location = location.split("#", 1)[0].split("?", 1)[0]
                if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", location) and not location.startswith("file:"):
                    return
                if location.startswith("file:"):
                    location = location[5:]
                candidate = (root / location).resolve()
                try:
                    relative = candidate.relative_to(root.resolve())
                except ValueError:
                    relative = None
                if relative is not None and relative.parts and relative.parts[0] in groups:
                    domain = relative.parts[0]
                    target = groups[domain].get(candidate.stem)
                    if (len(relative.parts) != 2 or candidate.suffix != ".md"
                            or target is None or not candidate.is_file()):
                        raise ContractError(f"missing local record reference: {value['location']}")
                    if (value["id"] != target["id"]
                            or value["revision"] not in versions[target["id"]]):
                        raise ContractError(f"local reference ID/revision mismatch: {value['location']}")
            for label, expected_type in RELATIONS.items():
                if label in value:
                    for item in relation_items(value[label], label):
                        record_id = item if isinstance(item, str) else item["id"]
                        target = groups["design"].get(record_id)
                        if target is None or target["type"].casefold() != expected_type:
                            raise ContractError(f"{label}: missing or wrong-type design point {record_id}")
            for item in value.values():
                visit(item)
    for records in groups.values():
        for record in records.values():
            visit(record)


def validate_projects(groups, project_root):
    if not Path(project_root).is_dir():
        raise ContractError(f"project registry is not a directory: {project_root}")
    for record in groups["tasks"].values():
        for metadata in [record, *[entry["metadata"] for entry in record.get("history", [])]]:
            keys = set(values(metadata.get("project repository"), "project repository"))
            for point in values(metadata.get("head sha"), "head sha"):
                keys.add(project_refs.parse_ref(point, "point")["project key"])
            for label in ("working branch", "integration branch"):
                for area in values(metadata.get(label), label):
                    keys.add(project_refs.parse_ref(area, "area")["project key"])
            for key in keys:
                project_refs.project_config(project_root, key)


def cell(value):
    if value is None or value == "":
        return "-"
    return (str(value).replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>")
            .replace("<!--", "&lt;!--").replace("-->", "--&gt;"))


def spec_value(value):
    if value is None:
        return "-"
    if isinstance(value, dict):
        if all(k in value for k in ("id", "revision", "location")):
            return f"{value['id']}@{value['revision']}"
        return "{" + "; ".join(f"{k}: {spec_value(v)}" for k, v in value.items()
                                if v is not None and v != [] and v != {}) + "}"
    if isinstance(value, list):
        return ", ".join(spec_value(item) for item in value) or "-"
    return str(value)


def detail_spec(record, domain):
    common = set(DESIGN_COLUMNS if domain == "design" else TASK_COLUMNS)
    parts = []
    for key, value in record.items():
        if key in common or value is None or value == [] or value == {}:
            continue
        if key == "history":
            summary = ", ".join(item["metadata"]["revision"] for item in value)
        else:
            summary = spec_value(value)
        label = "relate to " + RELATIONS[key] if key in RELATIONS else key
        if key == "gists":
            label = "gists (reference only)"
        parts.append(f"{label}: {summary}")
    lines = [line for part in parts
             for line in re.split(r"\r\n?|\n|<br\s*/?>", part, flags=re.IGNORECASE)]
    if (len(lines) > DETAIL_SPEC_MAX_LINES
            or sum(map(len, lines)) > DETAIL_SPEC_MAX_CHARS):
        remaining = DETAIL_SPEC_MAX_CHARS - len("...")
        shortened = []
        for line in lines[:DETAIL_SPEC_MAX_LINES]:
            shortened.append(line[:remaining])
            remaining -= len(shortened[-1])
            if remaining == 0:
                break
        shortened[-1] += "..."
        lines = shortened
    return "<br>".join(cell(line) for line in lines) or "-"


def render_index(records, domain):
    columns = DESIGN_COLUMNS if domain == "design" else TASK_COLUMNS
    headers = [*columns, "detail spec"]
    lines = ["| " + " | ".join(headers) + " |",
             "| " + " | ".join("---" for _ in headers) + " |"]
    for record_id, record in sorted(records.items()):
        cells = []
        for column in columns:
            value = record.get(column)
            if column == "id":
                value = f"[{record_id}]({domain}/{record_id}.md)"
            elif isinstance(value, (list, dict)):
                value = spec_value(value)
            cells.append(cell(value))
        cells.append(detail_spec(record, domain))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_topology(records):
    """Dependencies point to consumers; node identifiers never contain user text."""
    nodes = {record_id: f"n{index}" for index, record_id in enumerate(sorted(records))}
    lines = ["```mermaid", "flowchart TD"]
    for record_id, record in sorted(records.items()):
        label = f"{record_id}: {record['title']} ({record['state']})"
        label = escape(label, quote=True).replace("\\", "&#92;").replace("`", "&#96;")
        label = label.replace("\r", " ").replace("\n", " ")
        lines.append(f'    {nodes[record_id]}["{label}"]')
    for record_id, record in sorted(records.items()):
        for dependency in sorted(record["depends on"]):
            if dependency not in nodes:
                raise ContractError(f"unknown task dependency: {dependency}")
            lines.append(f"    {nodes[dependency]} --> {nodes[record_id]}")
    lines.append("```")
    return "\n".join(lines)


def validate_feature(root, groups=None):
    groups = collect(root) if groups is None else groups
    status = root / "STATUS.md"
    if not status.is_file():
        raise ContractError("missing STATUS.md")
    reject_transient_refs(status.read_text(encoding="utf-8-sig"), "STATUS.md")
    for domain, filename in (("design", "DESIGN.md"), ("tasks", "TASKS.md")):
        content = (root / filename).read_text(encoding="utf-8-sig")
        left, right = region_bounds(content, f"{domain}-preview-table")
        outside = content[:left] + content[right:]
        actual = content[left:right].strip()
        if actual != render_index(groups[domain], domain):
            raise ContractError(f"{filename}: table differs from YAML; update with feature_indexes.py --write")
        if domain == "tasks":
            left, right = region_bounds(content, "tasks-dependency-topology-mermaid")
            if content[left:right].strip() != render_topology(groups["tasks"]):
                raise ContractError("TASKS.md: topology differs from YAML; update with feature_indexes.py --write")
            # Do not mistake generated annotations for authoritative body citations.
            left, right = region_bounds(outside, "tasks-dependency-topology-mermaid")
            outside = outside[:left] + outside[right:]
        reject_transient_refs(outside, filename)
    # VERBAL.md and gists/ are intentionally not read, resolved or required.
    return {"design": len(groups["design"]), "tasks": len(groups["tasks"])}


def main(argv=None):
    # Markdown/JSON output is UTF-8 even when Windows pipes default to a locale codec.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="One design/task detail or a Feature directory")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--render", choices=("design", "tasks", "topology"), help="Print generated content; never write it")
    parser.add_argument("--project-root", type=Path, help="Optional project registry root")
    args = parser.parse_args(argv)
    try:
        if args.path.is_dir():
            groups = collect(args.path, args.project_root)
            if args.render:
                print(render_topology(groups["tasks"]) if args.render == "topology"
                      else render_index(groups[args.render], args.render))
                return 0
            counts = validate_feature(args.path, groups)
            result = {"valid": True, "scope": "structure-only", **counts,
                      "project registry": "checked" if args.project_root else "unverified"}
        elif args.path.suffix.casefold() in (".yaml", ".yml"):
            if args.render:
                raise ContractError("--render requires a Feature directory")
            project = project_refs.load_project(args.path)
            result = {"valid": True, "scope": "structure-only",
                      "project key": project["project key"]}
        else:
            if args.render:
                raise ContractError("--render requires a Feature directory")
            record = load(args.path)
            domain = record_domain(record, args.path.parent.name
                                   if args.path.parent.name in ("design", "tasks") else None)
            if domain == "tasks" and args.project_root is not None:
                validate_projects({"tasks": {record["id"]: record}}, args.project_root)
            result = {"valid": True, "scope": "structure-only", "id": record["id"],
                      "type": record["type"], "revision": record.get("revision"),
                      "project registry": ("checked" if args.project_root else "unverified")
                                          if domain == "tasks" else "not applicable"}
    except (ContractError, project_refs.ProjectRefError, OSError, ValueError, UnicodeError) as exc:
        result = {"valid": False, "scope": "structure-only", "error": str(exc)}
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False))
    elif result["valid"]:
        print("VALID STRUCTURE; authority and business policy not verified")
    else:
        print(result["error"], file=sys.stderr)
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
