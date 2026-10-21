#!/usr/bin/env python3
"""Fixed generated-region boundaries; preserve all unmanaged text verbatim."""

from __future__ import annotations

import re

REGIONS = {
    "design-preview-table": ("DESIGN.md", "preview-table"),
    "tasks-preview-table": ("TASKS.md", "preview-table"),
    "tasks-dependency-topology-mermaid": ("TASKS.md", "dependency-topology"),
    "verbal-preview-table": ("VERBAL.md", "preview-table"),
}


class BlockError(ValueError):
    pass


def fence_spans(content):
    """Spans include opening/closing lines; an unclosed fence ends at EOF."""
    fence = None
    offset = 0
    start = 0
    for line in content.splitlines(keepends=True):
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$",
                         line.lstrip("\ufeff") if offset == 0 else line)
        if match:
            token, rest = match.groups()
            if fence is None:
                if token[0] != "`" or "`" not in rest:
                    fence, start = token, offset
            elif token[0] == fence[0] and len(token) >= len(fence) and not rest.strip():
                yield start, offset + len(line)
                fence = None
        offset += len(line)
    if fence is not None:
        yield start, len(content)


def fenced_at(content, position):
    """Ignore apparent headings/markers inside Markdown fenced examples."""
    return any(left <= position < right for left, right in fence_spans(content))


def mask_fenced_code(content):
    """Remove code from syntax scans, preserving line breaks and offsets."""
    parts = []
    position = 0
    for left, right in fence_spans(content):
        parts.extend((content[position:left],
                      re.sub(r"[^\r\n]", " ", content[left:right])))
        position = right
    return "".join([*parts, content[position:]])


def region_bounds(content, name):
    """Return the body span only; markers must lead their fixed H2 section."""
    _, heading = REGIONS[name]
    markers = [f"<!-- {name}:{edge} -->" for edge in ("start", "end")]
    matches = []
    for marker in markers:
        occurrences = [match for match in re.finditer(re.escape(marker), content)
                       if not fenced_at(content, match.start())]
        if len(occurrences) != 1:
            raise BlockError(f"{name}: expected exactly one marker pair")
        # The first textual occurrence may belong to an earlier fenced example.
        match = next((candidate for candidate in re.finditer(
            r"^" + re.escape(marker) + r"[ \t]*\r?$", content, re.MULTILINE)
            if candidate.start() == occurrences[0].start()), None)
        if match is None:
            raise BlockError(f"{name}: markers must be on standalone lines")
        matches.append(match)
    start, end = matches
    if start.start() >= end.start():
        raise BlockError(f"{name}: markers are reversed")
    section = [match for match in re.finditer(
        r"^## " + re.escape(heading) + r"[ \t]*\r?$", content, re.MULTILINE)
        if not fenced_at(content, match.start())]
    if len(section) != 1:
        raise BlockError(f"{name}: expected one ## {heading} section")
    section = section[0]
    if any(fenced_at(content, match.start()) for match in (section, start, end)):
        raise BlockError(f"{name}: section and markers cannot be inside a fenced example")
    if section.end() >= start.start() or content[section.end():start.start()].strip():
        raise BlockError(f"{name}: start marker must immediately follow ## {heading}")
    body_start = content.find("\n", start.end()) + 1
    if not body_start or body_start > end.start():
        raise BlockError(f"{name}: start marker must end with a newline")
    body = content[body_start:end.start()]
    if (re.search(r"^ {0,3}#{1,6}(?:[ \t]+|\r?$)", body, re.MULTILINE)
            or re.search(r"^ {0,3}\S[^\r\n]*\r?\n {0,3}(?:=+|-+)[ \t]*\r?$",
                         body, re.MULTILINE)):
        raise BlockError(f"{name}: generated block crosses a section")
    return body_start, end.start()


def replace_regions(content, replacements):
    """Validate all requested spans before replacing any of them."""
    spans = []
    newline = "\r\n" if "\r\n" in content else "\n"
    for name, rendered in replacements.items():
        left, right = region_bounds(content, name)
        body = rendered.replace("\r\n", "\n").rstrip("\n").replace("\n", newline) + newline
        spans.append((left, right, body))
    spans.sort()
    if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
        raise BlockError("generated blocks overlap")
    for left, right, body in reversed(spans):
        content = content[:left] + body + content[right:]
    for name in replacements:
        region_bounds(content, name)
    return content
