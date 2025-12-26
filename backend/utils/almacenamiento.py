import json
from pathlib import Path
from utils.esquema import initial_game_state

# backend/state/game_state.json
STATE_PATH = Path(__file__).resolve().parents[1] / "state" / "game_state.json"


def load_state() -> dict:
    """
    Carga el estado desde JSON. Si no existe (o está vacío), crea uno inicial.
    """
    if not STATE_PATH.exists() or STATE_PATH.stat().st_size == 0:
        state = initial_game_state()
        save_state(state)
        return state

    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    """
    Guarda el estado en JSON (bonito y legible).
    """
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def reset_state() -> dict:
    """
    Reinicia el estado (útil para pruebas).
    """
    state = initial_game_state()
    save_state(state)
    return state