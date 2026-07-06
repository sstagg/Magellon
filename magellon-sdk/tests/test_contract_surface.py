"""CONTRACT.md drift gate.

Executes every ``python`` code fence in CONTRACT.md §2.1 — the promised
plugin-author import surface. If the document promises an import that
no longer resolves (or was renamed without updating the contract), this
fails. This is exactly the drift that let a removed ``TaskDto`` alias
stay documented for three minor releases.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

CONTRACT = Path(__file__).resolve().parents[1] / "CONTRACT.md"


def _section_2_1() -> str:
    text = CONTRACT.read_text(encoding="utf-8")
    match = re.search(r"### 2\.1 .*?(?=\n### |\n## )", text, flags=re.S)
    assert match, "CONTRACT.md §2.1 not found — update this test if renumbered"
    return match.group(0)


def _code_fences(section: str) -> list[str]:
    return re.findall(r"```python\n(.*?)```", section, flags=re.S)


def test_promised_import_surface_resolves():
    fences = _code_fences(_section_2_1())
    assert fences, "no python code fences in §2.1"
    for fence in fences:
        # Each fence is straight import statements (+ comments).
        exec(compile(fence, str(CONTRACT), "exec"), {})


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
