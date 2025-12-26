from datetime import datetime

def initial_game_state():
    return {
        "meta": {
            "version": 1,
            "created_at": datetime.utcnow().isoformat(),
            "turn": 0
        },

        "player": {
            "id": "player_1",
            "name": "Jugador",
            "class": "Aventurero",
            "level": 1,
            "hp": 20,
            "max_hp": 20,
            "stats": {
                "attack": 5,
                "defense": 2
            },
            "inventory": [],
            "gold": 0,
            "location": "inicio",
            "status_effects": []  # ej: "poisoned"
        },

        "world": {
            "current_scene": {
                "type": "exploration",  # exploration | combat | dialogue
                "location": "inicio",
                "active_enemy_ids": [],
                "active_npc_ids": []
            },

            "visited_locations": ["inicio"],

            "locations": {
                "inicio": {
                    "name": "Punto de partida",
                    "description": "Un lugar tranquilo donde empieza la aventura.",
                    "connected_to": []
                }
            },

            "enemies": {},     # {"goblin_1": {...}}
            "npcs": {},        # {"npc_1": {...}}
            "items": {},       # {"item_1": {...}}

            "quests": {
                "active": [],
                "completed": []
            }
        },

        "flags": {
            # "boss_bosque_derrotado": False
        },

        "narrative_memory": {
            "summary": "La aventura acaba de comenzar.",
            "last_events": [],
            "important_facts": []  # cosas que NUNCA deben cambiar
        },

        "logs": {
            "actions": []  # historial breve de inputs del jugador
        }
    }