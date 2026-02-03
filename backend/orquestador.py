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

    # 2) Routing: si estamos en combate -> agente de combate, si no -> narrador.
    scene = state.get("world", {}).get("current_scene", {}) or {}
    scene_type = scene.get("type", "exploration")

    text_low = (player_input or "").lower()

    # Palabras clave para detectar intención de combate / acciones
    wants_combat = any(k in text_low for k in ["combate", "bandido", "enemigo"])
    action_kw_present = any(k in text_low for k in [
        "ataco", "atacar", "ataque", "pego", "golpeo",
        "empuj", "esquiv", "defiend",
        "huir", "huyo", "escap", "fuerte"
    ])

    # Si el usuario solo "entra en combate" (sin acción concreta), iniciamos el encuentro
    # pero NO resolvemos un turno todavía: mostramos menú y esperamos acción.
    start_only = (scene_type != "combat") and wants_combat and (not action_kw_present)

    # Si el usuario ya escribe una acción (p.ej. "ataco") y no hay combate activo, iniciamos y resolvemos en el mismo input.
    # Solo empezamos combate automáticamente si hay intención clara de combate (no solo verbos)
    start_and_act = (scene_type != "combat") and wants_combat

    if start_only or start_and_act:
        # Inicializamos escena de combate
        state.setdefault("world", {}).setdefault("current_scene", {}).update({
            "type": "combat",
            "location": scene.get("location", state.get("player", {}).get("location", "inicio")),
            "active_enemy_ids": scene.get("active_enemy_ids", []),
            "active_npc_ids": scene.get("active_npc_ids", []),
            "combat_status": {
                "player_skip_next": False,
                "enemy_skip_next": False,
                "enemy_disadvantage": False,
            }
        })
        scene_type = "combat"

        # ✅ Garantizar enemigo vivo
        enemy_id = _ensure_active_enemy_alive(state)
        enemies = state.setdefault("world", {}).setdefault("enemies", {})
        enemy_hp = enemies.get(enemy_id, {}).get("hp", 0)
        enemy_name = enemies.get(enemy_id, {}).get("name", "Bandido")

        if start_only:
            # Guardamos el estado y devolvemos menú interactivo
            save_state(state)
            return {
                "text": (
                    f"¡{enemy_name} te corta el paso! (HP {enemy_hp})\n\n"
                    "¿Qué decides hacer? (atacar / ataque fuerte / empuje / esquivo / defiendo / huir)"
                ),
                "image": None
            }

    # 3) Ejecutar agente
    if scene_type == "combat":
        result = combat_agent(state, player_input)
    else:
        result = narrador_agent(state, player_input)

    # 4) Aplicar updates y guardar
    state = apply_updates(state, result.get("updates", {}))

    # ✅ Si el narrador activó combate, garantizar enemigo vivo también
    scene2 = state.get("world", {}).get("current_scene", {}) or {}
    if scene2.get("type") == "combat":
        _ensure_active_enemy_alive(state)

    save_state(state)

    # 5) Respuesta estándar
    return {
        "text": result.get("text", ""),
        "image": None
    }
