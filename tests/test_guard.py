"""Guards that keep the ablation series clean: no V2+ mechanisms in V1 (and the shared code and baselines),
no V3+ mechanisms in V2."""

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


def v1_sources():
    """V1, the shared code and the baselines; the version-agnostic harness and later versions are excluded."""
    # baselines/b3.py is a V2-era reference condition (reflective carry-over), not part of V1's comparison set
    return [p for p in sources() if (p.parent.name in ("v1", "common", "baselines") or p == PACKAGE / "cli.py")
            and p != PACKAGE / "baselines" / "b3.py"]


def test_no_imports_of_later_version_modules():
    offenders = []
    for path in v1_sources():
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
    assert not {p.stem for p in v1_sources()} & FORBIDDEN_MODULES


def test_no_later_version_terms_in_v1_code_or_prompts():
    offenders = []
    for path in v1_sources():
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


# ---------- V2: nothing from V3+ ----------

V2_PACKAGE = PACKAGE / "v2"
# Alice7 modules of later versions (and of nothing in the series: facets, identity, people)
V3_MODULES = {"affect", "stream", "mind", "drift", "wake", "waking", "sleep", "traits", "attention", "activities",
              "imagination", "selfedit", "facets", "identity", "people", "tools", "reloader", "pressure", "voice"}
V3_TERMS = re.compile(
    r"\b(valence|arousal|mood|affect|appraisal|emotions?|temperament|stream_thoughts|selfedit|prompt_versions|"
    r"facets?|traits?|consolidat\w*|hibernate|pressure)\b", re.I)


def v2_sources():
    return sorted(V2_PACKAGE.rglob("*.py"))


def test_v2_exists_and_imports_no_later_mechanisms():
    assert v2_sources()
    offenders = []
    for path in v2_sources():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [a.name for a in node.names]
            for name in names:
                if set(name.split(".")) & V3_MODULES or name.split(".")[0] in ("threading", "sched", "asyncio"):
                    offenders.append(f"{path.relative_to(PACKAGE)}: {name}")
    assert not offenders, offenders
    assert not {p.stem for p in v2_sources()} & V3_MODULES


def test_no_later_version_terms_in_v2():
    """No affect, sleep, background processes, self-editing prompts, facets or traits (spec §3.2)."""
    offenders = [f"{p.relative_to(PACKAGE)}:{i}: {line.strip()}"
                 for p in v2_sources() for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
                 if V3_TERMS.search(line)]
    assert not offenders, offenders


def test_v2_has_no_timers_or_autonomous_messages():
    """V2 changes only when a turn or a session end happens: no timers, no threads, no messages of its own."""
    for path in v2_sources():
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\bThread\(|\bTimer\(|time\.sleep\(|add_message\(", text), path


# ---------- V3: nothing from V4 ----------

V3_PACKAGE = PACKAGE / "v3"
V4_TERMS = re.compile(r"\b(traits?|curiosity_level|initiative_trait|empathy_trait|drives?|attractors?|coalitions?)\b",
                      re.I)


def v3_agent_sources():
    """V3 agent code; the interactive CLI may run a timer thread, the agent itself may not."""
    return [p for p in sorted(V3_PACKAGE.rglob("*.py")) if p.name != "cli.py"]


def test_v3_exists_and_has_no_v4_mechanisms():
    assert v3_agent_sources()
    offenders = [f"{p.relative_to(PACKAGE)}:{i}: {line.strip()}"
                 for p in v3_agent_sources() for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
                 if V4_TERMS.search(line)]
    assert not offenders, offenders


def test_v3_agent_lives_through_simulated_time_only():
    """Silence is lived through advance(to) on the sim clock: no threads, timers or sleeping in the agent."""
    for path in v3_agent_sources():
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\bimport threading|\bThread\(|\bTimer\(|time\.sleep\(", text), path
