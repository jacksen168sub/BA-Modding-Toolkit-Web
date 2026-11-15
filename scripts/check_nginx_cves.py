#!/usr/bin/env python3
"""nginx CVE gate for the auto-bump pipeline.

Decides whether a candidate nginx version may be released, and renders the
"what did this bump fix" section used in PR checks and GitHub Releases.

Exit codes
  0  ok (proceed / nothing to do)
  2  blocked: the target introduces a major severity CVE that the current
     version does not have, or the target is older than the current version
  3  data error: advisories page unreachable, unparsable, or too few entries,
     or a version could not be determined. Never treated as "no vulnerabilities".

Why "Not vulnerable" must be parsed
  The `Vulnerable:` spans on nginx.org are global, not per-branch. CVE-2026-15176
  says `Vulnerable: 0.1.29-1.31.6`, which contains 1.30.6 - yet 1.30.6 is fixed
  (`Not vulnerable: 1.31.7+, 1.30.6+`). Judging by the vulnerable span alone
  reports 12 findings against 1.30.6 instead of 1, and every release note would
  claim the shipped image is affected by a pile of already-fixed CVEs.
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ADVISORIES_URL = "https://nginx.org/en/security_advisories.html"
EOL_URL = "https://endoflife.date/api/nginx.json"

# The live page carries 60+ entries. A structural change upstream (or an
# interstitial error page) shows up as a tiny number, which must fail closed.
MIN_ENTRIES = 30

# Severities that are worth reporting. "none" entries (e.g. CVE-2009-4487,
# "error log data are not sanitized") carry `Vulnerable: all`, so they would sit
# in every release note forever; "minor" is pre-2010 noise with no fixed version.
REPORTED_SEVERITIES = ("low", "medium", "major")

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UA = "bamt-nginx-cve-gate/1.0 (+https://github.com/jacksen168sub/BA-Modding-Toolkit-Web)"


class DataError(RuntimeError):
    """Raised when an upstream data source cannot be trusted."""


# --------------------------------------------------------------------------- #
# fetching
# --------------------------------------------------------------------------- #
def fetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (https only)
        return resp.read().decode("utf-8", "replace")


# --------------------------------------------------------------------------- #
# parsing the advisory page
# --------------------------------------------------------------------------- #
_TAG_RE = re.compile(r"<[^>]+>")
_CVE_RE = re.compile(r"(CVE-\d{4}-\d+|VU#\d+|CORE-\d{4}-\d+)")
_ITEM_RE = re.compile(r"<li>\s*<p>(.*?)</p>\s*</li>", re.S | re.I)
_BR_RE = re.compile(r"<br\s*/?>", re.I)


def _clean(fragment: str) -> str:
    text = _TAG_RE.sub(" ", fragment)
    text = html_mod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_advisories(page: str) -> list[dict]:
    """Turn the advisory page into [{cve, severity, not_vulnerable, vulnerable}]."""
    entries: list[dict] = []
    for block in _ITEM_RE.findall(page):
        # Each item is one line per <br>: title / Severity: / Advisory / CVE / Not vulnerable / Vulnerable
        fields: dict[str, str] = {"title": "", "severity": "", "cve": "", "not_vulnerable": "", "vulnerable": ""}
        for index, raw in enumerate(_BR_RE.split(block)):
            # splitting on the tag leaves the closing '>' behind ("...<br>Severity:")
            piece = _clean(raw).lstrip(">").strip()
            if not piece:
                continue
            if index == 0 and not fields["title"]:
                fields["title"] = piece
            lowered = piece.lower()
            if lowered.startswith("severity:"):
                fields["severity"] = piece.split(":", 1)[1].strip().lower()
            elif lowered.startswith("not vulnerable:"):
                fields["not_vulnerable"] = piece.split(":", 1)[1].strip()
            elif lowered.startswith("vulnerable:"):
                fields["vulnerable"] = piece.split(":", 1)[1].strip()
            elif not fields["cve"]:
                match = _CVE_RE.search(piece)
                if match:
                    fields["cve"] = match.group(1)
        if fields["cve"] and fields["vulnerable"]:
            entries.append(fields)
    return entries


# --------------------------------------------------------------------------- #
# version maths
# --------------------------------------------------------------------------- #
def parse_version(text: str) -> tuple[int, ...]:
    parts = [int(p) for p in re.findall(r"\d+", text)[:3]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def _span_contains(span: str, version: tuple[int, ...]) -> bool:
    span = span.strip()
    if not span:
        return False
    if span.lower() == "all":
        return True
    if span.lower() == "none":
        return False
    span = re.sub(r"^nginx/windows\s*", "", span, flags=re.I)

    lowered = re.fullmatch(r"(\d+(?:\.\d+)*)\s*[-–]\s*(\d+(?:\.\d+)*)", span)
    if lowered:
        return parse_version(lowered.group(1)) <= version <= parse_version(lowered.group(2))
    plus = re.fullmatch(r"(\d+(?:\.\d+)*)\s*\+", span)
    if plus:
        return version >= parse_version(plus.group(1))
    exact = re.fullmatch(r"(\d+(?:\.\d+)*)", span)
    if exact:
        return parse_version(exact.group(1)) == version
    raise DataError(f"unparsable version span: {span!r}")


def spans_contain(spec: str, version: tuple[int, ...]) -> bool:
    return any(_span_contains(part, version) for part in spec.split(",") if part.strip())


def branch_fixes(not_vulnerable: str) -> dict[tuple[int, int], tuple[int, ...]]:
    """'1.31.7+, 1.30.6+' -> {(1, 31): (1,31,7), (1, 30): (1,30,6)}"""
    fixes: dict[tuple[int, int], tuple[int, ...]] = {}
    for part in not_vulnerable.split(","):
        match = re.fullmatch(r"\s*(\d+)\.(\d+)\.(\d+)\+?\s*", part)
        if match:
            fixes[(int(match.group(1)), int(match.group(2)))] = parse_version(
                f"{match.group(1)}.{match.group(2)}.{match.group(3)}"
            )
    return fixes


def is_affected(entry: dict, version_text: str) -> bool:
    """Affected = inside the global vulnerable span AND below this branch's fix."""
    version = parse_version(version_text)
    if not spans_contain(entry["vulnerable"], version):
        return False
    fix = branch_fixes(entry["not_vulnerable"]).get((version[0], version[1]))
    if fix is None:
        return True  # this branch has no fix listed -> still vulnerable
    return version < fix


def _reported(entries: list[dict]) -> list[dict]:
    return [e for e in entries if e["severity"] in REPORTED_SEVERITIES]


# --------------------------------------------------------------------------- #
# evaluation
# --------------------------------------------------------------------------- #
def evaluate(entries: list[dict], current: str, target: str) -> dict:
    """Compare two versions. Raises DataError on unusable input."""
    for label, value in (("current", current), ("target", target)):
        if not re.fullmatch(r"\d+(?:\.\d+){1,2}", value or ""):
            raise DataError(f"{label} version is empty or malformed: {value!r}")

    reported = _reported(entries)
    affected_current = {e["cve"]: e for e in reported if is_affected(e, current)}
    affected_target = {e["cve"]: e for e in reported if is_affected(e, target)}

    fixed = [e for cve, e in affected_current.items() if cve not in affected_target]
    newly_affected = [e for cve, e in affected_target.items() if cve not in affected_current]
    new_major = [e for e in newly_affected if e["severity"] == "major"]

    downgrade = parse_version(target) < parse_version(current)
    blocked = bool(new_major) or downgrade

    reasons = []
    if downgrade:
        reasons.append(f"target {target} is older than current {current}")
    for entry in new_major:
        reasons.append(f"{entry['cve']} (major) does not affect {current} but affects {target}")

    return {
        "current": current,
        "target": target,
        "blocked": blocked,
        "reasons": reasons,
        "fixed": fixed,
        "still_affected": list(affected_target.values()),
        "newly_affected": newly_affected,
        "entries": len(entries),
    }


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def render_markdown(result: dict) -> str:
    lines = [f"## nginx {result['current']} → {result['target']}", ""]
    if result["blocked"]:
        lines += ["> **BLOCKED** — this bump would introduce new major findings:", ""]
        lines += [f"- {reason}" for reason in result["reasons"]]
        lines.append("")
    lines.append(f"### 本次修掉 ({len(result['fixed'])})")
    if result["fixed"]:
        lines += [
            f"- `{e['cve']}` {e['severity']} — {e['title']}（affected {e['vulnerable']}，fixed in {e['not_vulnerable']}）"
            for e in result["fixed"]
        ]
    else:
        lines.append("- 无")
    lines.append("")
    lines.append(f"### 仍影响 {result['target']} ({len(result['still_affected'])})")
    if result["still_affected"]:
        lines += [f"- `{e['cve']}` {e['severity']} — {e['title']}" for e in result["still_affected"]]
    else:
        lines.append("- 无")
    lines.append("")
    lines.append(f"<sub>advisory 条目 {result['entries']} 条；来源 https://nginx.org/en/security_advisories.html</sub>")
    return "\n".join(lines) + "\n"


def render_text(result: dict) -> str:
    head = "BLOCKED" if result["blocked"] else "OK"
    out = [f"[{head}] nginx {result['current']} -> {result['target']}",
           f"  fixed={len(result['fixed'])} still_affected={len(result['still_affected'])} entries={result['entries']}"]
    for reason in result["reasons"]:
        out.append(f"  ! {reason}")
    for entry in result["fixed"]:
        out.append(f"  - fixed {entry['cve']} ({entry['severity']})")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# inputs
# --------------------------------------------------------------------------- #
def current_version_from_repo() -> str:
    script = REPO_ROOT / "scripts" / "nginx-version.sh"
    if not script.exists():
        raise DataError(f"missing {script}")
    proc = subprocess.run(["sh", str(script)], capture_output=True, text=True, cwd=REPO_ROOT)
    version = proc.stdout.strip()
    if not version:
        raise DataError("scripts/nginx-version.sh produced no version (Dockerfile ENV NGINX_VERSION missing?)")
    return version


def load_advisories(args: argparse.Namespace) -> tuple[list[dict], str]:
    if args.advisories_file:
        page = Path(args.advisories_file).read_text(encoding="utf-8", errors="replace")
        source = args.advisories_file
    else:
        try:
            page = fetch(ADVISORIES_URL, timeout=args.timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise DataError(f"cannot fetch {ADVISORIES_URL}: {exc}") from exc
        source = ADVISORIES_URL
    entries = parse_advisories(page)
    if len(entries) < MIN_ENTRIES:
        raise DataError(
            f"only {len(entries)} advisories parsed from {source} (expected >= {MIN_ENTRIES}); "
            "page layout changed or fetch was intercepted - refusing to guess"
        )
    return entries, source


# --------------------------------------------------------------------------- #
# watchdog
# --------------------------------------------------------------------------- #
def run_watchdog(entries: list[dict], current: str, body_out: str | None) -> int:
    try:
        payload = json.loads(fetch(EOL_URL, timeout=30))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise DataError(f"cannot fetch {EOL_URL}: {exc}") from exc

    major, minor = parse_version(current)[:2]
    cycle = next((c for c in payload if c.get("cycle") == f"{major}.{minor}"), None)
    if cycle is None:
        raise DataError(f"endoflife.date has no cycle {major}.{minor} for nginx")

    eol = cycle.get("eol", False)
    latest = cycle.get("latest")
    alerts = []
    if eol not in (False, None):
        alerts.append(f"nginx {major}.{minor} 已 EOL（{eol}），当前锁 {current}，需要人工决定是否升 minor")
    if latest and parse_version(latest) > parse_version(current):
        alerts.append(f"同一分支已发布 {latest}（当前锁 {current}）—— 若 Renovate 没有提 PR，说明检测链路可能坏了")

    title = f"nginx {major}.{minor} watchdog"
    summary = "\n".join(f"- {a}" for a in alerts) if alerts else f"nginx {major}.{minor} 正常，当前 {current}，EOL={eol}"
    print(f"[watchdog] {title}\n{summary}")

    body = f"当前锁定：`{current}`\n\n{summary}\n"
    if body_out:
        Path(body_out).write_text(body, encoding="utf-8")

    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as handle:
            handle.write(f"alert={'true' if alerts else 'false'}\n")
            handle.write(f"title={title}\n")
    return 0


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="nginx CVE gate / release-note generator")
    parser.add_argument("--current", help="version currently pinned (default: read from Dockerfile)")
    parser.add_argument("--target", help="candidate version; omit to only report the current state")
    parser.add_argument("--advisories-file", help="use a local copy of the advisory page (offline)")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--markdown", action="store_true", help="markdown output (PR summary / release notes)")
    parser.add_argument("--watchdog", action="store_true", help="EOL / branch-rotation check")
    parser.add_argument("--body-out", help="with --watchdog: also write the issue body to this file")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        entries, _source = load_advisories(args)
        current = args.current or current_version_from_repo()

        if args.watchdog:
            return run_watchdog(entries, current, args.body_out)

        target = args.target
        if not target:
            affected = [e for e in _reported(entries) if is_affected(e, current)]
            result = {
                "current": current,
                "target": current,
                "blocked": False,
                "reasons": [],
                "fixed": [],
                "still_affected": affected,
                "newly_affected": [],
                "entries": len(entries),
            }
        else:
            result = evaluate(entries, current, target)

        if args.json:
            print(json.dumps({k: v for k, v in result.items()}, ensure_ascii=False, indent=2))
        elif args.markdown:
            sys.stdout.write(render_markdown(result))
        else:
            sys.stdout.write(render_text(result))

        if result["blocked"]:
            return 2
        return 0
    except DataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
