def initial_game_state():
    return {
        "meta": {"version": 1},
        "player": {
            "name": "Jugador",
            "hp": 20,
            "inventory": [],
            "location": "inicio"
        },
        "world": {
            "visited_locations": ["inicio"],
            "enemies": {},
            "items": {},
            "quests": []
        },
        "flags": {},
        "narrative_memory": {
            "summary": "La aventura acaba de comenzar.",
            "last_events": []
        }
    }