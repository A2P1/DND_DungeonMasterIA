def narrator_agent(game_state: dict, player_input: str) -> dict:
    """
    Prototipo: genera texto sin IA y propone updates simples.
    """
    location = game_state["player"]["location"]
    turn = game_state["meta"]["turn"]

    text = (
        f"[Turno {turn}] Estás en '{location}'.\n"
        f"Tú: {player_input}\n\n"
        "Narrador (prototipo): Algo ocurre en el mundo... (aún sin IA)."
    )

    # updates: lo mínimo para probar el pipeline
    updates = {
        "narrative_memory": {
            "last_events_append": f"Turno {turn}: el jugador dijo '{player_input}'"
        }
    }

    return {"text": text, "updates": updates}