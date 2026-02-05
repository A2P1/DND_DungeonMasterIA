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
        if "current_scene" in w_updates and isinstance(
            w_updates["current_scene"], dict
        ):
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

        # --- Pending locations (lugares propuestos por el narrador) ---
        if "propose_location" in w_updates and isinstance(
            w_updates["propose_location"], dict
        ):
            pl = w_updates["propose_location"]
            w.setdefault("pending_locations", [])
            pl_id = pl.get("id")
            if isinstance(pl_id, str) and pl_id:
                exists = any(
                    isinstance(x, dict) and x.get("id") == pl_id
                    for x in w["pending_locations"]
                )
                if not exists:
                    w["pending_locations"].append(pl)

        if w_updates.get("clear_pending_locations") is True:
            w["pending_locations"] = []

        # --- Mapa dinámico (100% IA) ---
        if "add_location" in w_updates and isinstance(w_updates["add_location"], dict):
            loc = w_updates["add_location"]
            loc_id = loc.get("id")
            if isinstance(loc_id, str) and loc_id:
                w.setdefault("locations", {})
                if loc_id not in w["locations"]:
                    w["locations"][loc_id] = {
                        "name": loc.get("name", loc_id),
                        "description": loc.get("description", ""),
                        "connected_to": loc.get("connected_to", []),
                    }

        if (
            "connect_locations" in w_updates
            and isinstance(w_updates["connect_locations"], list)
            and len(w_updates["connect_locations"]) == 2
        ):
            a, b = w_updates["connect_locations"][0], w_updates["connect_locations"][1]
            w.setdefault("locations", {})
            if a in w["locations"] and b in w["locations"]:
                w["locations"][a].setdefault("connected_to", [])
                w["locations"][b].setdefault("connected_to", [])
                if b not in w["locations"][a]["connected_to"]:
                    w["locations"][a]["connected_to"].append(b)
                if a not in w["locations"][b]["connected_to"]:
                    w["locations"][b]["connected_to"].append(a)

        # Resto de claves a nivel world
        for k, v in w_updates.items():
            if k in (
                "current_scene",
                "visited_locations_append",
                "propose_location",
                "clear_pending_locations",
                "add_location",
                "connect_locations",
            ):
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
    - routing narrador/combate
    - aplicar updates
    - si acaba combate: narrador automático
    - guardar estado
    - devolver texto
    """
    state = load_state()

    # 1) Incrementar turno y loggear acción
    state.setdefault("meta", {}).setdefault("turn", 0)
    state["meta"]["turn"] += 1

    state.setdefault("logs", {}).setdefault("actions", [])
    state["logs"]["actions"].append(player_input)

    # 2) Routing
    scene = state.get("world", {}).get("current_scene", {}) or {}
    scene_type = scene.get("type", "exploration")

    text_low = (player_input or "").lower()
    wants_combat = any(
        k in text_low
        for k in [
            "combate",
            "entro en combate",
            "enemigo",
            "bandido",
            "goblin",
            "goblins",
        ]
    )

    if scene_type != "combat" and wants_combat:
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

        state.setdefault("world", {}).setdefault("current_scene", {}).update(
            {
                "type": "combat",
                "location": scene.get(
                    "location", state.get("player", {}).get("location", "inicio")
                ),
                "active_enemy_ids": ["bandido_1"],
                "active_npc_ids": scene.get("active_npc_ids", []),
                "combat_status": {
                    "player_skip_next": False,
                    "enemy_skip_next": False,
                    "enemy_disadvantage": False,
                },
            }
        )
        scene_type = "combat"

    # 2.5) Ejecutar agente
    if scene_type == "combat":
        result = combat_agent(state, player_input)
    else:
        result = narrador_agent(state, player_input)

    # 3) Aplicar updates y guardar
    state = apply_updates(state, result.get("updates", {}))
    save_state(state)

    # ✅ 3.5) Si el combate terminó, llama al narrador automáticamente
    # Preferimos el flag combat_end si existe (más fiable)
    combat_end = result.get("combat_end")

    # Fallback: detectar por cambio de escena (por si todavía no tienes combat_end)
    was_combat_turn = (scene_type == "combat")
    now_scene_type = (state.get("world", {}).get("current_scene", {}) or {}).get("type", "exploration")
    combat_ended_by_scene = was_combat_turn and now_scene_type != "combat"

    if combat_end or combat_ended_by_scene:
        # Construimos el input para el narrador (string)
        if combat_end:
            res = combat_end.get("result", "victory")
            enemy_ids = combat_end.get("enemy_ids", [])
            loc = combat_end.get("location", (state.get("player", {}) or {}).get("location", "inicio"))

            post_input = (
                "POST-COMBATE:\n"
                f"- Resultado: {res}\n"
                f"- Enemigos implicados/derrotados: {enemy_ids}\n"
                f"- Ubicación actual: {loc}\n\n"
                "Narra brevemente el desenlace y continúa la historia desde la situación actual. "
                "No repitas las tiradas; céntrate en el resultado, el entorno y las consecuencias. "
                "Termina con: ¿Qué haces?"
            )
        else:
            post_input = (
                "POST-COMBATE:\n"
                "El combate ha terminado. Narra brevemente el desenlace y continúa la historia desde "
                "la situación actual. No repitas las tiradas; céntrate en el resultado y el entorno. "
                "Termina con: ¿Qué haces?"
            )

        narr = narrador_agent(state, post_input)

        # aplicar updates del narrador y guardar
        state = apply_updates(state, narr.get("updates", {}))
        save_state(state)

        return {
            "text": result.get("text", "").rstrip() + "\n\n" + narr.get("text", ""),
            "image": None
        }

    # 4) Respuesta estándar
    return {
        "text": result.get("text", ""),
        "image": None
    }
