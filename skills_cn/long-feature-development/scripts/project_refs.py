#!/usr/bin/env python3
"""Resolve project-qualified commit points and branch areas without Git or network."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

try:
    import yaml
except ImportError:
    yaml = None


class ProjectRefError(ValueError):
    pass


KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
SHA = re.compile(r"[0-9a-fA-F]{7,64}\Z")


if yaml is not None:
    class ProjectLoader(yaml.SafeLoader):
        pass

    # Preserve dates as source strings so arbitrary basic rules remain JSON-safe.
    ProjectLoader.yaml_implicit_resolvers = {
        key: [(tag, pattern) for tag, pattern in values
              if tag != "tag:yaml.org,2002:timestamp"]
        for key, values in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }

    def unique_mapping(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise ProjectRefError("project YAML keys must be unique strings")
            result[key] = loader.construct_object(value_node, deep=deep)
        return result

    ProjectLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def parse_ref(value, kind="point"):
    if kind not in ("point", "area"):
        raise ProjectRefError("reference kind must be point or area")
    if not isinstance(value, str) or "@" not in value:
        raise ProjectRefError("reference must include project-key@value")
    project, rest = value.split("@", 1)
    if not KEY.fullmatch(project) or not rest or any(c.isspace() for c in rest):
        raise ProjectRefError("invalid project-qualified reference")
    if kind == "area":
        return {"kind": kind, "project key": project, "branch": rest,
                "canonical": value}
    branch = None
    sha = rest
    if "@" in rest:
        branch, sha = rest.rsplit("@", 1)
        if not branch:
            raise ProjectRefError("full point reference requires a branch name")
    if not SHA.fullmatch(sha):
        raise ProjectRefError("point reference requires a literal hexadecimal commit SHA")
    return {"kind": kind, "project key": project, "branch": branch,
            "sha": sha.lower(), "canonical": f"{project}@{sha.lower()}",
            "abbreviated": len(sha) not in (40, 64)}


def validate_project(record):
    if not isinstance(record, dict):
        raise ProjectRefError("project configuration must be a YAML mapping")
    project = record.get("project key")
    if not isinstance(project, str) or not KEY.fullmatch(project):
        raise ProjectRefError("project key must be a stable identifier")
    remote = record.get("remote repository")
    if not isinstance(remote, str) or not remote.strip():
        raise ProjectRefError("remote repository must be a nonempty locator")
    local = record.get("local repository")
    if isinstance(local, str):
        valid_local = bool(local.strip())
    else:
        valid_local = (isinstance(local, dict) and bool(local)
                       and all(isinstance(k, str) and k.strip()
                               and isinstance(v, str) and v.strip() for k, v in local.items()))
    if not valid_local:
        raise ProjectRefError("local repository must be a locator or a device/OS-to-locator mapping")
    if any(key in record for key in ("head sha", "working branch", "integration branch")):
        raise ProjectRefError("moving work state belongs to tasks, not project configuration")
    return record


def load_project(path):
    if yaml is None:
        raise ProjectRefError("PyYAML is required for project configuration")
    try:
        record = yaml.load(Path(path).read_text(encoding="utf-8-sig"), Loader=ProjectLoader)
    except yaml.YAMLError as exc:
        raise ProjectRefError(f"invalid project YAML: {exc}") from exc
    return validate_project(record)


def project_config(project_root, project_key):
    if not isinstance(project_key, str) or not KEY.fullmatch(project_key):
        raise ProjectRefError("invalid project key")
    root = Path(project_root).resolve()
    path = root / project_key / "project.yaml"
    if not path.resolve().is_relative_to(root):
        raise ProjectRefError("project configuration escapes project root")
    record = load_project(path)
    if record["project key"] != project_key:
        raise ProjectRefError("project folder and project key disagree")
    return record


def resolve_ref(project_root, value, kind="point"):
    parsed = parse_ref(value, kind)
    return {"reference": parsed, "project": project_config(project_root, parsed["project key"]),
            "scope": "location-only", "commit verified": False}


def main(argv=None):
    # Markdown/JSON output is UTF-8 even when Windows pipes default to a locale codec.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("reference")
    parser.add_argument("--kind", choices=("point", "area"), default="point")
    args = parser.parse_args(argv)
    try:
        result = resolve_ref(args.project_root, args.reference, args.kind)
    except (ProjectRefError, OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"valid": True, **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
