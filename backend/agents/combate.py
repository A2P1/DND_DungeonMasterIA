from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from utils.dados import d20, disadvantage


# Características por defecto del jugador
DEFAULT_PLAYER = {
    "hp": 20,
    "ac": 12,
    "dc": 12,
    "attack_bonus": 2,
    "damage_normal": 5,
    "damage_strong": 9,
}
# Características por defecto de un bandido genérico
DEFAULT_BANDIT = {
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


def _get_player(state: Dict[str, Any]) -> Dict[str, Any]:
    p = state.setdefault("player", {})
    # Rellenas con valores por defecto si no existen 
    for k, v in DEFAULT_PLAYER.items():
        p.setdefault(k, v)
    # Mantiene un "max_hp" coherente 
    p.setdefault("max_hp", p.get("hp", DEFAULT_PLAYER["hp"]))
    return p

# Mantenemos una escena constante, para que cuando cambiemos entre narrador y combate, no se pierda información por el camino
def _ensure_scene(state: Dict[str, Any]) -> Dict[str, Any]:
    w = state.setdefault("world", {})
    scene = w.setdefault("current_scene", {})
    scene.setdefault("type", "exploration")
    scene.setdefault("location", state.get("player", {}).get("location", "inicio"))
    scene.setdefault("active_enemy_ids", [])
    scene.setdefault("active_npc_ids", [])
    # Flags de combate
    status = scene.setdefault("combat_status", {})
    status.setdefault("player_skip_next", False)
    status.setdefault("enemy_skip_next", False)
    status.setdefault("enemy_disadvantage", False)
    return scene

#Asegura que el enemigo existe y rellena los valores por defecto
def _ensure_enemy(state: Dict[str, Any], enemy_id: str) -> Dict[str, Any]:
    enemies = state.setdefault("world", {}).setdefault("enemies", {})
    enemy = enemies.setdefault(enemy_id, {})
    for k, v in DEFAULT_BANDIT.items():
        enemy.setdefault(k, v)
    enemy.setdefault("id", enemy_id)
    enemy.setdefault("max_hp", enemy.get("hp", DEFAULT_BANDIT["hp"]))
    return enemy

# Generamos a un enemigo activo que esté vivo y no haya escapado y lo devolvemos.
def _choose_active_enemy(state: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    scene = _ensure_scene(state)
    enemies = state.get("world", {}).get("enemies", {}) or {}
    for eid in scene.get("active_enemy_ids", []) or []:
        e = enemies.get(eid)
        if e and e.get("is_alive", True) and not e.get("escaped", False):
            _ensure_enemy(state, eid)
            return eid, state["world"]["enemies"][eid]
    return None


def _parse_player_action(text: str) -> str:
    """Parsea acciones del jugador en combate.
    Devuelve uno de: attack_normal, attack_strong, push, dodge, defend, flee, unknown.
    """
    # Damos formato al texto que escriba el usuario para procesarlo y facilitar el parseo.
    t = (text or "").lower().strip()

    # Diferentes palabras que puede escribir el usuario para huir.
    if any(k in t for k in ["huir", "huyo", "escapar", "escapo", "correr", "corro"]):
        return "flee"

    # # Diferentes palabras que puede escribir el usuario para empujar, defenderse o esquivar.
    if "empuj" in t:
        return "push"
    if any(k in t for k in ["esquivo", "esquivar", "esquiva", "dodge"]):
        return "dodge"
    if any(k in t for k in ["defiendo", "defender", "defensa", "bloqueo", "paro"]):
        return "defend"

    # # Diferentes palabras que puede escribir el usuario para atacar y atacar fuerte.
    if "fuerte" in t:
        # si menciona atacar + fuerte, lo tomamos como ataque fuerte
        if any(k in t for k in ["ataco", "atacar", "ataque", "golpeo", "pego", "golpear", "pegar"]):
            return "attack_strong"
        # si solo dice "fuerte" asumimos ataque fuerte igualmente
        return "attack_strong"

    if any(k in t for k in ["ataco", "atacar", "ataque", "golpeo", "pego", "golpear", "pegar"]):
        return "attack_normal"

    return "unknown"


# Función para resolver un turno de ataque, aplicando reglas del Dungeons & Dragons como el dado de 20 caras para resolver el conflicto.
def _attack_roll(attack_bonus: int, target_ac: int, strong: bool = False, with_disadvantage: bool = False) -> Tuple[int, int, bool]:
    base = disadvantage() if with_disadvantage else d20()
    penalty = 0
    if strong:
        penalty = 2  # Si elige el ataque fuerte, no contamos el bonus de + 2. El bonus en D&D no es bonus de daño, sino un bonus que se añade al valor del dado. Como es un ataque fuerte, es normal que cueste más acertar el golpe
    total = base + attack_bonus - penalty
    hit = total >= target_ac
    return base, total, hit

# Turnos del enemigo
def _bandit_decision(enemy: Dict[str, Any]) -> str:
    # Cuando tiene menos 2 puntos de vida, intenta huir
    if int(enemy.get("hp", 0)) <= 2:
        return "shout_flee"
    # El enemigo tiene una probabilidad de 25% de intentar un ataque fuerte, y un 75% de hacer un ataque normal.
    return "attack_strong" if random.random() < 0.25 else "attack_normal"

# Cuando termina un combate, comprueba si quedan más enemigos vivos en la escena. Si no quedan, cambia la escena de combate a exploración.
def _cleanup_scene_after_enemy_list(state: Dict[str, Any]) -> None:
    scene = _ensure_scene(state)
    enemies = state.get("world", {}).get("enemies", {}) or {}
    alive_ids = []
    for eid in scene.get("active_enemy_ids", []) or []:
        e = enemies.get(eid)
        if not e:
            continue
        if e.get("is_alive", True) and not e.get("escaped", False):
            alive_ids.append(eid)
    scene["active_enemy_ids"] = alive_ids
    if not alive_ids and scene.get("type") == "combat":
        scene["type"] = "exploration"

# Función principal que define cómo se desarrollan los combates
def combat_step(state: Dict[str, Any], player_input: str) -> Dict[str, Any]:
    """Resuelve un turno de combate (numérico) y aplica cambios directos al state."""
    player = _get_player(state)
    scene = _ensure_scene(state)
    status = scene.setdefault("combat_status", {})
    action = _parse_player_action(player_input)

    active = _choose_active_enemy(state)
    if not active:
        return {"error": "No hay enemigo activo en la escena.", "combat_ended": True}

    enemy_id, enemy = active

    # --- Acción no reconocida: no avanzamos el turno (no ataca el enemigo) ---
    if action == "unknown":
        return {
            "error": "Acción no válida. Escribe: atacar, ataque fuerte, empuje, esquivo, defiendo o huir.",
            "enemy_id": enemy_id,
            "enemy_name": enemy.get("name", enemy_id),
            "player": {"action": "unknown"},
            "enemy": None,
            "hp_after": {"player_hp": int(player.get("hp", 0)), "enemy_hp": int(enemy.get("hp", 0))},
            "enemy_dead": not enemy.get("is_alive", True),
            "player_dead": int(player.get("hp", 0)) <= 0,
            "combat_ended": False,
            "no_progress": True,
        }

    # --- Si el jugador está aturdido, pierde su acción ---
    player_skipped = False
    if status.get("player_skip_next", False):
        status["player_skip_next"] = False
        player_skipped = True
        action = "skip"

    # --- Turno del jugador ---
    player_event = {"action": action}
    combat_ended = False

    if action == "flee":
        roll = d20()
        success = roll >= int(player.get("dc", 12))
        player_event.update({"roll": roll, "success": success})
        if success:
            # Sale del combate
            scene["type"] = "exploration"
            scene["active_enemy_ids"] = []
            combat_ended = True
        # si falla, el enemigo tendrá su turno normal

    elif action in ("push", "dodge", "defend"):
        roll = d20()
        success = roll >= int(player.get("dc", 12))
        player_event.update({"roll": roll, "success": success})

        if success:
            if action == "push":
                status["enemy_skip_next"] = True
            elif action == "dodge":
                status["enemy_disadvantage"] = True
            elif action == "defend":
                status["enemy_skip_next"] = True

    elif action in ("attack_normal", "attack_strong"):
        strong = action == "attack_strong"
        base, total, hit = _attack_roll(int(player.get("attack_bonus", 2)), int(enemy.get("ac", 10)), strong=strong)
        dmg = int(player.get("damage_strong" if strong else "damage_normal", 0)) if hit else 0
        enemy["hp"] = max(0, int(enemy.get("hp", 0)) - dmg)
        if enemy["hp"] <= 0:
            enemy["is_alive"] = False
            combat_ended = True

        player_event.update({
            "attack_roll": base,
            "attack_total": total,
            "hit": hit,
            "damage": dmg,
        })

    elif action == "skip":
        player_event.update({"skipped": True})

    # --- Si el jugador ha escapado o el enemigo ha muerto, no ataca el enemigo ---
    if combat_ended:
        _cleanup_scene_after_enemy_list(state)
        return {
            "enemy_id": enemy_id,
            "enemy_name": enemy.get("name", enemy_id),
            "player": player_event,
            "enemy": None,
            "hp_after": {"player_hp": int(player.get("hp", 0)), "enemy_hp": int(enemy.get("hp", 0))},
            "enemy_dead": not enemy.get("is_alive", True),
            "player_dead": int(player.get("hp", 0)) <= 0,
            "combat_ended": True,
            "player_skipped": player_skipped,
        }

    # --- Turno del enemigo ---
    enemy_event: Dict[str, Any] = {"action": None}
    enemy_skipped = False

    if status.get("enemy_skip_next", False):
        status["enemy_skip_next"] = False
        enemy_skipped = True
        enemy_event = {"action": "skip", "skipped": True}
    else:
        enemy_action = _bandit_decision(enemy)
        enemy_event["action"] = enemy_action

        if enemy_action == "shout_flee":
            roll = d20()
            success = roll >= int(player.get("dc", 12))
            enemy_event.update({"roll": roll, "success": success})
            if success:
                # Paraliza al jugador 1 turno y huye
                status["player_skip_next"] = True
                enemy["escaped"] = True
                scene["active_enemy_ids"] = [eid for eid in scene.get("active_enemy_ids", []) if eid != enemy_id]
                _cleanup_scene_after_enemy_list(state)
                return {
                    "enemy_id": enemy_id,
                    "enemy_name": enemy.get("name", enemy_id),
                    "player": player_event,
                    "enemy": enemy_event,
                    "hp_after": {"player_hp": int(player.get("hp", 0)), "enemy_hp": int(enemy.get("hp", 0))},
                    "enemy_dead": False,
                    "player_dead": int(player.get("hp", 0)) <= 0,
                    "combat_ended": scene.get("type") != "combat",
                    "enemy_skipped": enemy_skipped,
                    "player_skipped": player_skipped,
                }

        elif enemy_action in ("attack_normal", "attack_strong"):
            strong = enemy_action == "attack_strong"
            with_disadv = bool(status.get("enemy_disadvantage", False))
            status["enemy_disadvantage"] = False

            # strong: un poco más difícil (penalty handled in _attack_roll)
            base, total, hit = _attack_roll(int(enemy.get("attack_bonus", 2)), int(player.get("ac", 12)), strong=strong, with_disadvantage=with_disadv)
            dmg = int(enemy.get("damage_strong" if strong else "damage_normal", 0)) if hit else 0
            player["hp"] = max(0, int(player.get("hp", 0)) - dmg)

            enemy_event.update({
                "attack_roll": base,
                "attack_total": total,
                "hit": hit,
                "damage": dmg,
                "disadvantage": with_disadv,
            })

    player_dead = int(player.get("hp", 0)) <= 0
    combat_ended = player_dead
    if player_dead:
        # Por simplicidad, salimos de combate
        scene["type"] = "exploration"
        scene["active_enemy_ids"] = []

    _cleanup_scene_after_enemy_list(state)

    return {
        "enemy_id": enemy_id,
        "enemy_name": enemy.get("name", enemy_id),
        "player": player_event,
        "enemy": enemy_event,
        "hp_after": {"player_hp": int(player.get("hp", 0)), "enemy_hp": int(enemy.get("hp", 0))},
        "enemy_dead": not enemy.get("is_alive", True),
        "player_dead": player_dead,
        "combat_ended": scene.get("type") != "combat",
        "enemy_skipped": enemy_skipped,
        "player_skipped": player_skipped,
    }


# Menú de opciones que aparecen cuando el jugador entra en combate
def _combat_menu() -> str:
    return "¿Qué decides hacer? (atacar / ataque fuerte / empuje / esquivo / defiendo / huir)"


def render_combat_turn(summary: dict) -> str:
    """Renderiza un turno de combate en formato interactivo"""
    enemy_name = summary.get("enemy_name", "Enemigo")
    hp = summary.get("hp_after", {}) or {}
    player_hp = hp.get("player_hp", "?")
    enemy_hp = hp.get("enemy_hp", "?")

    # Si hay error 
    if "error" in summary:
        return f"{summary['error']}\nHP -> Tú: {player_hp} | {enemy_name}: {enemy_hp}\n\n{_combat_menu()}"

    lines = []
    lines.append(f"--- COMBATE vs {enemy_name} ---")

    p = summary.get("player", {}) or {}
    e = summary.get("enemy", None)

    # Turno jugador
    action = p.get("action", "")
    if summary.get("player_skipped"):
        lines.append("Estás aturdido y pierdes tu turno.")
    elif action == "flee":
        lines.append(f"Intentas huir... d20={p.get('roll')} -> " + ("ÉXITO ✅" if p.get("success") else "FALLO ❌"))
        if p.get("success"):
            lines.append("Escapas del combate.")
    elif action in ("push", "dodge", "defend"):
        verb = {"push": "Empuje", "dodge": "Esquiva", "defend": "Defensa"}.get(action, action)
        lines.append(f"{verb}: d20={p.get('roll')} -> " + ("ÉXITO ✅" if p.get("success") else "FALLO ❌"))
        if p.get("success"):
            if action == "dodge":
                lines.append("Te mueves con rapidez: el enemigo atacará con desventaja.")
            else:
                lines.append("Tu maniobra funciona: el enemigo pierde su acción este turno.")
    elif action in ("attack_normal", "attack_strong"):
        label = "Ataque fuerte" if action == "attack_strong" else "Ataque"
        lines.append(f"{label}: d20={p.get('attack_roll')} total={p.get('attack_total')} -> " + ("IMPACTO ✅" if p.get("hit") else "FALLO ❌"))
        if p.get("hit"):
            lines.append(f"Daño infligido: {p.get('damage')}")
        else:
            lines.append("No infliges daño.")
    else:
        lines.append("Acción realizada.")

    # Turno enemigo (si procede)
    if e:
        lines.append("")
        if e.get("action") == "skip":
            lines.append(f"{enemy_name} está desorientado y pierde su acción.")
        elif e.get("action") == "shout_flee":
            lines.append(f"{enemy_name} grita e intenta huir... d20={e.get('roll')} -> " + ("ÉXITO ✅" if e.get("success") else "FALLO ❌"))
            if e.get("success"):
                lines.append("Te paraliza un instante y escapa.")
        elif e.get("action") in ("attack_normal", "attack_strong"):
            label = "Ataque fuerte" if e.get("action") == "attack_strong" else "Ataque"
            extra = " (con desventaja)" if e.get("disadvantage") else ""
            lines.append(f"{label} de {enemy_name}{extra}: d20={e.get('attack_roll')} total={e.get('attack_total')} -> " + ("IMPACTO ✅" if e.get("hit") else "FALLO ❌"))
            if e.get("hit"):
                lines.append(f"Daño recibido: {e.get('damage')}")
            else:
                lines.append("El enemigo falla. No recibes daño.")

    # HP y cierre
    lines.append("")
    lines.append(f"HP -> Tú: {player_hp} | {enemy_name}: {enemy_hp}")

    if summary.get("enemy_dead"):
        lines.append(f"Has derrotado a {enemy_name}.")
        lines.append("Sales del combate.")
    elif summary.get("player_dead"):
        lines.append("Has sido derrotado. Fin de la aventura.")
    elif summary.get("combat_ended"):
        lines.append("El combate ha terminado.")
    else:
        lines.append("")
        lines.append(_combat_menu())

    return "\n".join(lines)

# Empaquetamos toda la función para pasársela al orquestador, que se encargará de llamar a esta función cada vez que detecta que el jugador va a iniciar un combate
def combat_agent(game_state: dict, player_input: str) -> dict:
    """
    Agente de combate interactivo.
    Devuelve:
      - text: texto para el jugador (interactivo)
      - updates: cambios a aplicar por el orquestador
      - combat_end (opcional): metadatos para transición narrativa automática
    """
    world = game_state.setdefault("world", {})
    scene = world.setdefault("current_scene", {})
    enemies = world.setdefault("enemies", {})
    player = game_state.setdefault("player", {})

    location = scene.get("location", player.get("location", "inicio"))

    # 1) Ejecutar paso de combate
    summary = combat_step(game_state, player_input)

    # 2) Texto interactivo
    combat_text = render_combat_turn(summary)

    # 3) Construir updates a partir del summary
    updates: dict = {}

    # --- Player HP ---
    if "hp_after" in summary and "player_hp" in summary["hp_after"]:
        updates.setdefault("player", {})["hp"] = summary["hp_after"]["player_hp"]

    # --- Enemy HP / estado ---
    enemy_id = summary.get("enemy_id")
    if enemy_id and enemy_id in enemies:
        updates.setdefault("world", {}).setdefault("enemies", {}).setdefault(enemy_id, {})
        updates["world"]["enemies"][enemy_id]["hp"] = summary["hp_after"]["enemy_hp"]
        updates["world"]["enemies"][enemy_id]["is_alive"] = not summary.get("enemy_dead", False)

    # --- Fin de combate ---
    if summary.get("combat_ended"):
        updates.setdefault("world", {}).setdefault("current_scene", {})
        updates["world"]["current_scene"]["type"] = "exploration"
        updates["world"]["current_scene"]["active_enemy_ids"] = []

    # 4) Construir salida
    out = {
        "text": combat_text,
        "updates": updates,
    }

    # 5) Metadatos post-combate (para el orquestador)
    if summary.get("combat_ended"):
        result_str = "defeat" if summary.get("player_dead") else "victory"

        out["combat_end"] = {
            "result": result_str,
            "enemy_ids": [enemy_id] if summary.get("enemy_dead") else [],
            "location": location,
        }

    return out
