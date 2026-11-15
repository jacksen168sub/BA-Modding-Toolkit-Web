#!/usr/bin/env python3
"""Tests for scripts/check_nginx_cves.py.

Run with:  python scripts/test_check_nginx_cves.py
(also picked up by pytest, it is plain unittest)

The advisory page is replaced by a fixture so the tests are offline and stable.
The five "real" entries are copied from nginx.org as of 2026-11-14; the filler
entries only exist to clear the fail-closed threshold (MIN_ENTRIES) and must not
affect any 1.30.x result.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_nginx_cves.py"


def item(title: str, severity: str, cve: str, not_vulnerable: str, vulnerable: str) -> str:
    return (
        f"<li><p>{title}<br>Severity: {severity}<br>"
        f'<a href="https://example.invalid">Advisory</a><br>'
        f'<a href="https://example.invalid">{cve}</a><br>'
        f"Not vulnerable: {not_vulnerable}<br>Vulnerable: {vulnerable}</p></li>"
    )


REAL_ENTRIES = [
    item("Buffer overflow when using alias with rewrite", "medium",
         "CVE-2026-15176", "1.31.7+, 1.30.6+", "0.1.29-1.31.6"),
    item("Buffer overflow in script evaluation", "medium",
         "CVE-2026-93479", "1.31.7+, 1.30.6+", "1.31.2-1.31.6, 1.30.0-1.30.5"),
    item("Request body injection in HTTP/3", "medium",
         "CVE-2026-95101", "1.31.7+, 1.30.6+", "1.25.0-1.31.6"),
    item("Session forgery when using TLS session tickets", "medium",
         "CVE-2026-97629", "1.31.7+, 1.30.6+", "1.23.2-1.31.6"),
    item("Use-after-free when using asynchronous file I/O (AIO)", "medium",
         "CVE-2026-97205", "1.31.7+, 1.30.6+", "0.8.11-1.31.6"),
    # "none" severity + Vulnerable: all -> must never be reported again
    item("An error log data are not sanitized", "none",
         "CVE-2009-4487", "none", "all"),
]

FILLER_ENTRIES = [
    item(f"Filler advisory {i}", "low", f"CVE-2001-{1000 + i}", "0.5.1+", "0.1.0-0.5.0")
    for i in range(30)
]


def page(*entries: str) -> str:
    return "<html><body><ul>" + "".join(entries) + "</ul></body></html>"


class GateTests(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )

    def fixture(self, entries: list[str]) -> str:
        handle = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
        handle.write(page(*entries))
        handle.close()
        return handle.name

    # ------------------------------------------------------------------ #
    def test_1305_to_1306_fixes_the_five(self):
        path = self.fixture(REAL_ENTRIES + FILLER_ENTRIES)
        proc = self.run_script("--current", "1.30.5", "--target", "1.30.6",
                               "--advisories-file", path, "--markdown")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout
        for cve in ("CVE-2026-15176", "CVE-2026-93479", "CVE-2026-95101",
                    "CVE-2026-97629", "CVE-2026-97205"):
            self.assertIn(cve, out)
        self.assertIn("本次修掉 (5)", out)
        # 1.30.6 is fixed for all of them, and "none" severity is filtered out
        self.assertIn("仍影响 1.30.6 (0)", out)
        self.assertNotIn("CVE-2009-4487", out)

    def test_same_version_is_clean(self):
        path = self.fixture(REAL_ENTRIES + FILLER_ENTRIES)
        proc = self.run_script("--current", "1.30.6", "--target", "1.30.6",
                               "--advisories-file", path, "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["fixed"], [])
        self.assertEqual(data["still_affected"], [])
        self.assertFalse(data["blocked"])

    def test_vulnerable_span_alone_would_misjudge(self):
        """CVE-2026-15176 lists `Vulnerable: 0.1.29-1.31.6`, which contains 1.30.6.

        The Not-vulnerable line is what makes 1.30.6 clean; this guards against a
        regression to span-only comparison.
        """
        path = self.fixture(REAL_ENTRIES[:1] + FILLER_ENTRIES)
        proc = self.run_script("--current", "1.30.6", "--target", "1.30.6",
                               "--advisories-file", path, "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["still_affected"], [])

    def test_new_major_blocks(self):
        major_entry = item("Hypothetical major regression", "major",
                           "CVE-2099-0001", "1.30.10+", "1.30.7-1.30.9")
        path = self.fixture([major_entry] + REAL_ENTRIES + FILLER_ENTRIES)
        proc = self.run_script("--current", "1.30.6", "--target", "1.30.8",
                               "--advisories-file", path)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("CVE-2099-0001", proc.stdout)

    def test_downgrade_blocks(self):
        path = self.fixture(REAL_ENTRIES + FILLER_ENTRIES)
        proc = self.run_script("--current", "1.30.6", "--target", "1.30.5",
                               "--advisories-file", path)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("older than current", proc.stdout)

    def test_short_page_fails_closed(self):
        path = self.fixture(REAL_ENTRIES[:3])
        proc = self.run_script("--current", "1.30.5", "--target", "1.30.6",
                               "--advisories-file", path)
        self.assertEqual(proc.returncode, 3, proc.stdout)
        self.assertIn("refusing to guess", proc.stderr)

    def test_malformed_version_is_a_data_error(self):
        path = self.fixture(REAL_ENTRIES + FILLER_ENTRIES)
        proc = self.run_script("--current", "not-a-version", "--target", "1.30.6",
                               "--advisories-file", path)
        self.assertEqual(proc.returncode, 3, proc.stdout)

    def test_current_only_report(self):
        path = self.fixture(REAL_ENTRIES + FILLER_ENTRIES)
        proc = self.run_script("--current", "1.30.5", "--advisories-file", path, "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(len(data["still_affected"]), 5)   # the five medium entries, all fixed in 1.30.6
        self.assertTrue(all(e["severity"] != "none" for e in data["still_affected"]))


class RangeTests(unittest.TestCase):
    """Version-span parsing, exercised through the CLI to stay implementation-agnostic."""

    def run_script(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              capture_output=True, text=True, cwd=REPO_ROOT)

    def test_multi_span_and_plus(self):
        entries = [
            item("multi span", "medium", "CVE-2099-1000", "1.30.1+", "1.30.0, 1.29.0-1.29.2"),
            item("plus span", "medium", "CVE-2099-1001", "1.29.5+", "1.29.0+"),
        ] + FILLER_ENTRIES
        handle = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
        handle.write(page(*entries))
        handle.close()
        proc = self.run_script("--current", "1.29.0", "--target", "1.29.5",
                               "--advisories-file", handle.name, "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        fixed = {e["cve"] for e in json.loads(proc.stdout)["fixed"]}
        self.assertEqual(fixed, {"CVE-2099-1000", "CVE-2099-1001"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
