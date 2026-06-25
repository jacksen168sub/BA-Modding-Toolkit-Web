# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jacksen168sub

"""Upload filename black/whitelist validation service.

Rules are loaded from a JSON file (configurable via `UPLOAD_RULES_FILE` env
var or `settings.upload_rules_file`). When the file is missing or invalid,
built-in default rules are used.

Rule file format:
    {
        "mode": "whitelist",        // "whitelist" | "blacklist"
        "case_sensitive": false,    // optional, default false
        "rules": [
            {
                "pattern": "^.*\\.bundle$",   // Python regex
                "description": "仅允许 bundle 文件"  // optional
            }
        ]
    }

Semantics:
    - whitelist: filename MUST match at least one rule pattern
    - blacklist: filename MUST NOT match any rule pattern
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from threading import RLock
from typing import List, Optional, Tuple

from ..config import settings

logger = logging.getLogger(__name__)


# Built-in default rules — whitelist: allow all png/skel/atlas files and only
# bundle files whose names start with specific Blue Archive asset prefixes.
DEFAULT_RULES: dict = {
    "mode": "whitelist",
    "case_sensitive": False,
    "rules": [
        {
            "pattern": r"^.*\.(png|skel|atlas)$",
            "description": "Allow all png/skel/atlas files",
        },
        {
            "pattern": r"^assets-_mx-spinelobbies-.*\.bundle$",
            "description": "Allow spine lobbies bundles",
        },
        {
            "pattern": r"^assets-_mx-spinecharacters-.*\.bundle$",
            "description": "Allow spine characters bundles",
        },
        {
            "pattern": r"^prologdepengroup-assets-_mx-spinecharacters-.*\.bundle$",
            "description": "Allow prologue spine characters bundles",
        },
    ],
}


class UploadRuleError(Exception):
    """Raised when a filename violates the upload rules."""


class _CompiledRule:
    __slots__ = ("pattern", "description", "raw")

    def __init__(self, pattern: str, description: str = "", flags: int = 0):
        self.raw = pattern
        self.pattern = re.compile(pattern, flags)
        self.description = description or pattern

    def matches(self, filename: str) -> bool:
        return self.pattern.search(filename) is not None


class UploadRuleService:
    """Singleton-ish service that loads, compiles and applies upload rules.

    The rules file is read lazily on first use and cached. Call
    `reload()` to force a re-read (e.g. after the mounted file changes).
    """

    def __init__(self, rules_file: Optional[Path] = None):
        self._rules_file = rules_file
        self._lock = RLock()
        self._compiled: List[_CompiledRule] = []
        self._mode: str = "whitelist"
        self._case_sensitive: bool = False
        self._source: str = "default"
        self._loaded: bool = False

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #
    def reload(self) -> None:
        """Force reload rules from the configured file (or defaults)."""
        with self._lock:
            self._load_locked()

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._load_locked()

    def _load_locked(self) -> None:
        rules_file = self._rules_file or settings.upload_rules_file
        try:
            path = Path(rules_file) if rules_file else None
        except Exception:
            path = None

        if path and path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._apply_config(data, source=str(path))
                logger.info("Loaded upload rules from %s (mode=%s, %d rules)",
                            path, self._mode, len(self._compiled))
                self._loaded = True
                return
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Failed to load upload rules from %s: %s — falling back to defaults",
                    path, exc,
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "Unexpected error loading upload rules from %s: %s — falling back to defaults",
                    path, exc,
                )

        # Fallback: built-in defaults
        self._apply_config(DEFAULT_RULES, source="default")
        logger.info("Using default upload rules (mode=%s, %d rules)",
                    self._mode, len(self._compiled))
        self._loaded = True

    def _apply_config(self, data: dict, source: str) -> None:
        mode = str(data.get("mode", "whitelist")).lower().strip()
        if mode not in ("whitelist", "blacklist"):
            logger.warning("Unknown upload rule mode %r, defaulting to whitelist", mode)
            mode = "whitelist"

        case_sensitive = bool(data.get("case_sensitive", False))
        flags = 0 if case_sensitive else re.IGNORECASE

        raw_rules = data.get("rules", [])
        if not isinstance(raw_rules, list):
            raw_rules = []

        compiled: List[_CompiledRule] = []
        for idx, item in enumerate(raw_rules):
            pattern = None
            description = ""
            if isinstance(item, str):
                pattern = item
            elif isinstance(item, dict):
                pattern = item.get("pattern")
                description = str(item.get("description", "") or "")
            if not pattern or not isinstance(pattern, str):
                logger.warning("Skipping invalid rule #%d (no pattern): %r", idx, item)
                continue
            try:
                compiled.append(_CompiledRule(pattern, description, flags))
            except re.error as exc:
                logger.warning(
                    "Skipping invalid regex in rule #%d (%r): %s",
                    idx, pattern, exc,
                )

        if not compiled:
            logger.warning("No valid rules found in %s, falling back to defaults", source)
            self._apply_config(DEFAULT_RULES, source="default")
            return

        self._mode = mode
        self._case_sensitive = case_sensitive
        self._compiled = compiled
        self._source = source

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    def validate(self, filename: str) -> Tuple[bool, str]:
        """Return (ok, reason). On failure, reason describes why."""
        if not filename:
            return False, "Filename is empty"

        self._ensure_loaded()

        matched_rule = None
        for rule in self._compiled:
            if rule.matches(filename):
                matched_rule = rule
                break

        if self._mode == "whitelist":
            if matched_rule is not None:
                return True, ""
            return False, (
                f"File '{filename}' is not in the upload whitelist "
                f"(no rule matched)"
            )
        else:  # blacklist
            if matched_rule is None:
                return True, ""
            return False, (
                f"File '{filename}' is blocked by upload blacklist "
                f"rule: {matched_rule.description}"
            )

    def raise_if_invalid(self, filename: str) -> None:
        ok, reason = self.validate(filename)
        if not ok:
            raise UploadRuleError(reason)

    # ------------------------------------------------------------------ #
    # Introspection (used by the API endpoint that exposes rules to FE)
    # ------------------------------------------------------------------ #
    def snapshot(self) -> dict:
        """Return a serialisable view of the active rules."""
        self._ensure_loaded()
        return {
            "mode": self._mode,
            "case_sensitive": self._case_sensitive,
            "source": self._source,
            "rules": [
                {"pattern": r.raw, "description": r.description}
                for r in self._compiled
            ],
        }


# Module-level singleton — instantiated once, reused across requests.
_upload_rule_service: Optional[UploadRuleService] = None
_singleton_lock = RLock()


def get_upload_rule_service() -> UploadRuleService:
    global _upload_rule_service
    if _upload_rule_service is None:
        with _singleton_lock:
            if _upload_rule_service is None:
                _upload_rule_service = UploadRuleService()
    return _upload_rule_service
