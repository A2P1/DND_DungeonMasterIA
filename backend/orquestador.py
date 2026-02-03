from utils.almacenamiento import load_state, save_state
from agents.narrador import narrador_agent
from agents.combate import combat_agent


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
        w = state.setdefault("world", {})
        w_updates = updates["world"]

        # Merge seguro de current_scene (para no perder campos)
        if "current_scene" in w_updates and isinstance(w_updates["current_scene"], dict):
            w_scene = w.setdefault("current_scene", {})
            w_scene.update(w_updates["current_scene"])
            w["current_scene"] = w_scene

        # Append para visited_locations
        if "visited_locations_append" in w_updates:
            loc = w_updates["visited_locations_append"]
            if isinstance(loc, str) and loc:
                w.setdefault("visited_locations", [])
                if loc not in w["visited_locations"]:
                    w["visited_locations"].append(loc)

        # Resto de claves a nivel world
        for k, v in w_updates.items():
            if k in ("current_scene", "visited_locations_append"):
                continue
            w[k] = v

        state["world"] = w

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

    # 2) Routing: si estamos en combate -> agente de combate, si no -> narrador.
    # MVP: si el usuario indica intención de pelear y no hay combate activo, creamos
    # un encuentro con 1 bandido para poder probar el sistema.
    scene = state.get("world", {}).get("current_scene", {}) or {}
    scene_type = scene.get("type", "exploration")

    text_low = (player_input or "").lower()
    wants_combat = any(k in text_low for k in ["combate", "ataco", "ataque", "pego", "golpeo", "bandido"])

    if scene_type != "combat" and wants_combat:
        # Spawn de bandido_1 si no existe
        enemies = state.setdefault("world", {}).setdefault("enemies", {})
        if "bandido_1" not in enemies:
            enemies["bandido_1"] = {
                "name": "Bandido",
                "hp": 12,
                "max_hp": 12,
                "ac": 10,
                "attack_bonus": 2,
                "damage_normal": 3,
                "damage_strong": 6,
                "is_alive": True,
                "escaped": False,
            }

        state.setdefault("world", {}).setdefault("current_scene", {}).update({
            "type": "combat",
            "location": scene.get("location", state.get("player", {}).get("location", "inicio")),
            "active_enemy_ids": ["bandido_1"],
            "active_npc_ids": scene.get("active_npc_ids", []),
            "combat_status": {
                "player_skip_next": False,
                "enemy_skip_next": False,
                "enemy_disadvantage": False,
            }
        })
        scene_type = "combat"

    if scene_type == "combat":
        result = combat_agent(state, player_input)
    else:
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