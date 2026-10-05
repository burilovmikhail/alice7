"""The shared persona prompt: prompts/persona.md, identical across V1..V4."""

from pathlib import Path

PERSONA_PATH = Path(__file__).resolve().parents[2] / "prompts" / "persona.md"


def load_persona(path: Path | None = None) -> str:
    path = path or PERSONA_PATH
    if not path.exists():
        raise FileNotFoundError(f"persona prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()
