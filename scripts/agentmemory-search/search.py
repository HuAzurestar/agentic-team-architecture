#!/usr/bin/env python3
"""Read-only Agent Memory searches; Python 3.10+, standard library only."""

import argparse
import base64
import json
import math
import mimetypes
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


ENDPOINTS = {
    "search": "/agentmemory/search",
    "smart": "/agentmemory/smart-search",
    "lessons": "/agentmemory/lessons/search",
    "insights": "/agentmemory/insights/search",
    "vision": "/agentmemory/vision-search",
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("query", nargs="?", help="Search keywords or an image description")
    cli.add_argument("--kind", choices=ENDPOINTS, default="search")
    cli.add_argument("--api-url", default=os.getenv("AGENTMEMORY_URL", "http://127.0.0.1:3111"))
    cli.add_argument("--token-file", default=os.getenv("AGENTMEMORY_TOKEN_FILE"), help="Read a token from a mounted file; otherwise use AGENTMEMORY_TOKEN or AGENTMEMORY_SECRET")
    cli.add_argument("--limit", type=int, default=5, help="Maximum returned items (1-100; vision: 1-50)")
    cli.add_argument("--project", help="Exact project identifier; not supported by vision")
    cli.add_argument("--agent-id", help="Agent scope for search/smart; * means all agents")
    cli.add_argument("--layer", choices=["all", "memory", "observation"], help="Only send targetLayer when explicitly requested; requires newer Agent Memory code")
    cli.add_argument("--format", choices=["compact", "narrative", "full"], help="search only; default: compact")
    cli.add_argument("--token-budget", type=int, help="search only; default: 1500 estimated tokens")
    cli.add_argument("--min-confidence", type=float, help="lessons/insights only; default: 0.1")
    cli.add_argument("--no-lessons", action="store_true", help="smart only; omit additional lessons")
    cli.add_argument("--session-id", help="vision only; actually restricts image results to one session")
    images = cli.add_mutually_exclusive_group()
    images.add_argument("--image-file", type=Path, help="vision only; read a local reference image (max 8 MiB)")
    images.add_argument("--image-ref", help="vision only; managed image path on the Agent Memory server")
    cli.add_argument("--timeout", type=float, default=90, help="HTTP timeout in seconds (1-300)")
    return cli


def make_body(args):
    if not 1 <= args.limit <= (50 if args.kind == "vision" else 100):
        raise ValueError("limit must be 1-50 for vision or 1-100 otherwise")
    if not math.isfinite(args.timeout) or not 1 <= args.timeout <= 300:
        raise ValueError("timeout must be between 1 and 300 seconds")
    allowed = {
        "project": ("search", "smart", "lessons", "insights"),
        "agent_id": ("search", "smart"),
        "layer": ("search", "smart"),
        "format": ("search",),
        "token_budget": ("search",),
        "min_confidence": ("lessons", "insights"),
        "no_lessons": ("smart",),
        "session_id": ("vision",),
        "image_file": ("vision",),
        "image_ref": ("vision",),
    }
    for option, kinds in allowed.items():
        value = getattr(args, option)
        if value is not None and value is not False and args.kind not in kinds:
            raise ValueError(f"--{option.replace('_', '-')} is not supported by {args.kind}")
    query = (args.query or "").strip()
    if args.kind == "vision":
        if query and (args.image_file or args.image_ref):
            raise ValueError("vision accepts either query text or one reference image, not both")
        body = {"topK": args.limit}
        if args.image_file:
            if args.image_file.stat().st_size > 8 * 1024 * 1024:
                raise ValueError("reference image exceeds 8 MiB")
            mime = mimetypes.guess_type(str(args.image_file))[0] or "application/octet-stream"
            if not mime.startswith("image/"):
                raise ValueError("reference image must have a recognized image extension")
            encoded = base64.b64encode(args.image_file.read_bytes()).decode("ascii")
            body["queryImageBase64"] = f"data:{mime};base64,{encoded}"
        elif args.image_ref:
            body["queryImageRef"] = args.image_ref
        elif query:
            body["queryText"] = query
        else:
            raise ValueError("vision requires a description, --image-file or --image-ref")
        if args.session_id:
            body["sessionId"] = args.session_id
        return body
    if not query:
        raise ValueError("a non-empty query is required")
    body = {"query": query, "limit": args.limit}
    if args.project:
        body["project"] = args.project
    if args.kind in ("search", "smart"):
        if args.agent_id:
            body["agentId"] = args.agent_id
        if args.layer:
            body["targetLayer"] = args.layer
        if args.kind == "smart":
            body["includeLessons"] = not args.no_lessons
        else:
            body["format"] = args.format or "compact"
            body["token_budget"] = args.token_budget if args.token_budget is not None else 1500
            if body["token_budget"] < 1:
                raise ValueError("token-budget must be positive")
    else:
        confidence = args.min_confidence if args.min_confidence is not None else 0.1
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("min-confidence must be between 0 and 1")
        body["minConfidence"] = confidence
    return body


def read_token(args):
    if args.token_file:
        token = Path(args.token_file).read_text(encoding="utf-8-sig").strip()
    else:
        token = (os.getenv("AGENTMEMORY_TOKEN") or os.getenv("AGENTMEMORY_SECRET") or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if "\n" in token or "\r" in token:
        raise ValueError("token must be a single line")
    return token


def search(args, body, token):
    base = urlsplit(args.api_url)
    if base.scheme not in ("http", "https") or not base.hostname or base.username or base.password or base.query or base.fragment or base.path.rstrip("/") not in ("", "/agentmemory"):
        raise ValueError("api-url must be an http(s) service URL without credentials, query or fragment")
    url = f"{base.scheme}://{base.netloc}{ENDPOINTS[args.kind]}"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers=headers, method="POST")
    # Local service requests must not inherit a system HTTP proxy or follow redirects.
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=args.timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("API response must be a JSON object")
    if result.get("success") is False or result.get("error"):
        raise ValueError(str(result.get("error") or "search failed"))
    return result


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    token = ""
    try:
        body = make_body(args)
        token = read_token(args)
        result = search(args, body, token)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except HTTPError as exc:
        message = f"HTTP {exc.code}: {exc.reason}"
        if exc.code == 401:
            message += "; check AGENTMEMORY_TOKEN or --token-file"
    except URLError as exc:
        message = f"Cannot reach Agent Memory: {exc.reason}"
    except (OSError, ValueError) as exc:
        message = str(exc)
    if token:
        message = message.replace(token, "[redacted]")
    print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
