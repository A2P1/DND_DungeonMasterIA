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

        if "propose_location" in w_updates and isinstance(w_updates["propose_location"], dict):
            pl = w_updates["propose_location"]
            w.setdefault("pending_locations", [])
            pl_id = pl.get("id")
            if isinstance(pl_id, str) and pl_id:
                exists = any(isinstance(x, dict) and x.get("id") == pl_id for x in w["pending_locations"])
                if not exists:
                    w["pending_locations"].append(pl)
        
        #Limpiar pendientes cuando el jugador visita una nueva ubicación
        if w_updates.get("clear_pending_locations") is True:
            w["pending_locations"] = []

        # Append para visited_locations
        if "visited_locations_append" in w_updates:
            loc = w_updates["visited_locations_append"]
            if isinstance(loc, str) and loc:
                w.setdefault("visited_locations", [])
                if loc not in w["visited_locations"]:
                    w["visited_locations"].append(loc)

        # Resto de claves a nivel world
        for k, v in w_updates.items():
            if k in ("current_scene", "visited_locations_append", "propose_location", "clear_pending_locations"):
                continue
            w[k] = v

        state["world"] = w

    return state


def _spawn_bandit(state: dict) -> str:
    """
    Crea un bandido NUEVO con ID único y stats base.
    """
    world = state.setdefault("world", {})
    enemies = world.setdefault("enemies", {})

    # crear id único: bandido_1, bandido_2, ...
    i = 1
    while f"bandido_{i}" in enemies:
        i += 1
    enemy_id = f"bandido_{i}"

    enemies[enemy_id] = {
        "name": f"Bandido {i}",
        "hp": 12,
        "max_hp": 12,
        "ac": 10,
        "attack_bonus": 2,
        "damage_normal": 3,
        "damage_strong": 6,
        "is_alive": True,
        "escaped": False,
    }
    return enemy_id


def _ensure_active_enemy_alive(state: dict) -> str:
    """
    Garantiza que el enemigo activo (active_enemy_ids[0]) exista y esté vivo.
    Si no existe o está muerto, spawnea uno nuevo y lo setea como activo.
    """
    world = state.setdefault("world", {})
    scene = world.setdefault("current_scene", {})
    enemies = world.setdefault("enemies", {})

    active_ids = scene.get("active_enemy_ids") or []
    enemy_id = active_ids[0] if active_ids else None

    # si no hay enemigo o no existe -> spawnea uno nuevo
    if not enemy_id or enemy_id not in enemies:
        new_id = _spawn_bandit(state)
        scene["active_enemy_ids"] = [new_id]
        return new_id

    enemy = enemies[enemy_id]
    if enemy.get("hp", 0) <= 0 or enemy.get("is_alive") is False or enemy.get("escaped") is True:
        new_id = _spawn_bandit(state)
        scene["active_enemy_ids"] = [new_id]
        return new_id

    return enemy_id


def handle_turn(player_input: str) -> dict:
    """
    Un turno completo del juego:
    - cargar estado
    - incrementar turno
    - registrar acción
    - llamar a agente (narrador o combate)
    - aplicar updates
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
    text_low = (player_input or "").lower().strip()

    # --- 2.1) COMBAT_PENDING: aquí NO se llama al narrador ---
    if scene_type == "combat_pending":
        confirm = any(k in text_low for k in ["sí", "si", "entro", "combate", "lucho", "peleo", "vale", "ok"])
        deny = any(k in text_low for k in ["no", "me voy", "retroced", "huir", "huyo", "escapo"])

        if confirm:
            # Elegimos tipo de enemigo pendiente (si no está, inferimos por memoria)
            pending_type = (scene.get("pending_enemy_type") or "").strip().lower()
            if not pending_type:
                last_events = (state.get("narrative_memory", {}) or {}).get("last_events", []) or []
                last = (last_events[-1] if last_events else "").lower()
                pending_type = "goblin" if "goblin" in last else "bandido"

            enemies = state.setdefault("world", {}).setdefault("enemies", {})

            # MVP: 1 enemigo
            if pending_type == "goblin":
                enemy_id = "goblin_1"
                enemies[enemy_id] = {
                    "id": enemy_id,
                    "name": "Goblin",
                    "hp": 8,
                    "max_hp": 8,
                    "ac": 11,
                    "attack_bonus": 2,
                    "damage_normal": 3,
                    "damage_strong": 5,
                    "is_alive": True,
                    "escaped": False,
                }
            else:
                enemy_id = _spawn_bandit(state)

            state.setdefault("world", {}).setdefault("current_scene", {}).update({
                "type": "combat",
                "location": scene.get("location", state.get("player", {}).get("location", "inicio")),
                "active_enemy_ids": [enemy_id],
                "active_npc_ids": scene.get("active_npc_ids", []),
                "combat_status": {
                    "player_skip_next": False,
                    "enemy_skip_next": False,
                    "enemy_disadvantage": False,
                }
            })

            save_state(state)
            enemy_hp = enemies.get(enemy_id, {}).get("hp", 0)
            enemy_name = enemies.get(enemy_id, {}).get("name", enemy_id)
            return {
                "text": (
                    f"¡{enemy_name} te corta el paso! (HP {enemy_hp})\n\n"
                    "¿Qué decides hacer? (atacar / ataque fuerte / empuje / esquivo / defiendo / huir)"
                ),
                "image": None,
            }

        if deny:
            state.setdefault("world", {}).setdefault("current_scene", {}).update({
                "type": "exploration",
                "active_enemy_ids": [],
            })
            save_state(state)
            return {
                "text": "Decides no enfrentarte y te alejas con cautela.\n\n¿Qué haces ahora?",
                "image": None,
            }

        # Si no confirma ni niega, repetimos pregunta
        return {
            "text": "¿Quieres entrar en combate? Responde 'sí' o 'no'.",
            "image": None,
        }

    # --- 2.2) COMBAT: ejecuta combate ---
    if scene_type == "combat":
        # Seguridad: si no hay enemigo activo, spawneamos uno (evita el 'HP ?')
        _ensure_active_enemy_alive(state)
        result = combat_agent(state, player_input)
    else:
        # --- 2.3) EXPLORATION/DIALOGUE: ejecuta narrador ---
        result = narrador_agent(state, player_input)

    # 3) Aplicar updates
    state = apply_updates(state, result.get("updates", {}))

    # 4) Si acaba el combate, llamamos al narrador automáticamente
    combat_end = result.get("combat_end")
    was_combat_turn = (scene_type == "combat")
    now_scene_type = (state.get("world", {}).get("current_scene", {}) or {}).get("type", "exploration")
    combat_ended_by_scene = was_combat_turn and now_scene_type != "combat"

    if combat_end or combat_ended_by_scene:
        loc = (combat_end or {}).get("location") or (state.get("player", {}) or {}).get("location", "inicio")
        res = (combat_end or {}).get("result", "victory")
        enemy_ids = (combat_end or {}).get("enemy_ids", [])

        post_input = (
            "POST-COMBATE:\n"
            f"- Resultado: {res}\n"
            f"- Enemigos implicados/derrotados: {enemy_ids}\n"
            f"- Ubicación actual: {loc}\n\n"
            "Narra brevemente el desenlace y continúa la historia desde la situación actual. "
            "No repitas las tiradas; céntrate en el resultado, el entorno y las consecuencias. "
            "Termina con: ¿Qué haces ahora?"
        )
        narr = narrador_agent(state, post_input)
        state = apply_updates(state, narr.get("updates", {}))
        save_state(state)
        return {
            "text": result.get("text", "").rstrip() + "\n\n" + narr.get("text", ""),
            "image": None,
        }

    # 5) Guardar y responder
    save_state(state)
    return {"text": result.get("text", ""), "image": None}