"""Guard: no V2+ mechanisms in V1 code, schema or prompts (keeps the ablation baseline clean)."""

import ast
import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "alice"

# Module names from Alice7 that belong to later versions
FORBIDDEN_MODULES = {"affect", "lessons", "learning", "persona", "stream", "facets", "identity", "introspection",
                     "drift", "mind", "selfedit", "traits", "attention", "activities", "imagination", "wake",
                     "waking", "sleep", "people", "tools", "reloader", "prompts_versions"}
# Schema / code terms of later mechanisms
FORBIDDEN_TERMS = re.compile(
    r"\b(valence|arousal|density|lessons?|reflect\w*|portraits?|beliefs?|feedback|facets?|(?<!user's )mood|"
    r"intentions?|opinions?|stream_thoughts|selfedit|prompt_versions|witness\w*|visibility)\b", re.I)


def sources():
    return [p for p in PACKAGE.rglob("*.py")]


def test_no_imports_of_later_version_modules():
    offenders = []
    for path in sources():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [a.name for a in node.names]
            for name in names:
                if set(name.split(".")) & FORBIDDEN_MODULES:
                    offenders.append(f"{path.relative_to(PACKAGE)}: {name}")
    assert not offenders, offenders
    assert not {p.stem for p in sources()} & FORBIDDEN_MODULES


def test_no_later_version_terms_in_v1_code_or_prompts():
    offenders = []
    for path in sources():
        if path.parts[-2] == "eval":  # the harness is version-agnostic and may describe later mechanisms
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if FORBIDDEN_TERMS.search(line):
                offenders.append(f"{path.relative_to(PACKAGE)}:{i}: {line.strip()}")
    persona = (PACKAGE.parent / "prompts" / "persona.md").read_text(encoding="utf-8")
    if FORBIDDEN_TERMS.search(persona):
        offenders.append("prompts/persona.md")
    assert not offenders, offenders


def test_no_agent_tools():
    for path in sources():
        text = path.read_text(encoding="utf-8")
        assert "tool_choice" not in text and '"tools"' not in text, path


def test_memory_time_comes_from_clock():
    """All timestamps come from Clock: datetime.now()/date.today() only inside clock.py."""
    for path in sources():
        if path.name == "clock.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"datetime\.now\(|date\.today\(|time\.time\(", text), path
