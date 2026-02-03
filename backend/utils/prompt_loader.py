from pathlib import Path

Prompts = Path(__file__).resolve().parents[1] / "prompts"

def load_prompt(filename: str) -> str:
    path = Prompts / filename
    return path.read_text(encoding="utf-8")