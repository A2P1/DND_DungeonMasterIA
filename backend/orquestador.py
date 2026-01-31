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

    # visited_locations_append (si viene un lugar nuevo)
    if "world" in updates and isinstance(updates["world"], dict):
        w_updates = updates["world"]

        # append de visited_locations
        if "visited_locations_append" in w_updates and isinstance(w_updates["visited_locations_append"], str):
            state.setdefault("world", {}).setdefault("visited_locations", [])
            loc = w_updates["visited_locations_append"]
            if loc not in state["world"]["visited_locations"]:
                state["world"]["visited_locations"].append(loc)

        # current_scene parcial
        if "current_scene" in w_updates and isinstance(w_updates["current_scene"], dict):
            state.setdefault("world", {}).setdefault("current_scene", {}).update(w_updates["current_scene"])

        # (si quieres) merge general de world (sin machacar listas/dicts complejos)
        # state.setdefault("world", {}).update({k: v for k, v in w_updates.items() if k not in ("visited_locations_append", "current_scene")})


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