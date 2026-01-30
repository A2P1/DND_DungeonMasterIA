from utils.almacenamiento import load_state, save_state
from agents.narrador import narrador_agent


def apply_updates(state: dict, updates: dict) -> dict:
    """
    Aplica cambios al estado. Mantén esto simple al principio.
    La idea: los agentes devuelven 'updates' y el orquestador los integra.
    """
    if not updates:
        return state

    # 1) Memoria narrativa: append de eventos
    if "narrative_memory" in updates:
        nm_updates = updates["narrative_memory"]
        nm = state.setdefault("narrative_memory", {"summary": "", "last_events": []})

        if "last_events_append" in nm_updates:
            nm.setdefault("last_events", []).append(nm_updates["last_events_append"])

        # Si algún día quieres actualizar summary:
        if "summary" in nm_updates and isinstance(nm_updates["summary"], str):
            nm["summary"] = nm_updates["summary"]

        state["narrative_memory"] = nm

    # 2) Player updates (si algún agente devuelve cambios del jugador)
    if "player" in updates and isinstance(updates["player"], dict):
        state.setdefault("player", {}).update(updates["player"])

    # 3) Flags
    if "flags" in updates and isinstance(updates["flags"], dict):
        state.setdefault("flags", {}).update(updates["flags"])

    # 4) World (cuidado: aquí podrías ser más granular)
    if "world" in updates and isinstance(updates["world"], dict):
        state.setdefault("world", {}).update(updates["world"])

    return state


def handle_turn(player_input: str) -> dict:
    """
    Un turno completo del juego:
    - cargar estado
    - incrementar turno
    - registrar acción
    - llamar a agente (por ahora narrador)
    - aplicar updates
    - guardar estado
    - devolver texto al frontend
    """
    state = load_state()

    # 1) Incrementar turno y loggear acción
    state.setdefault("meta", {}).setdefault("turn", 0)
    state["meta"]["turn"] += 1

    state.setdefault("logs", {}).setdefault("actions", [])
    state["logs"]["actions"].append(player_input)

    # 2) Llamar al agente adecuado (por ahora siempre narrador)
    result = narrador_agent(state, player_input)
    #print("DEBUG result =", result)

    # 3) Aplicar updates y guardar
    state = apply_updates(state, result.get("updates", {}))
    save_state(state)

    # 4) Respuesta estándar
    return {
        "text": result.get("text", ""),
        "image": None  # lo usaremos cuando metas el agente visual
    }