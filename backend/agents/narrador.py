import json

from config import get_llm
from prompts.sistema_narrador import SYSTEM_PROMPT

def narrador_agent(game_state: dict, player_input: str) -> dict:
    """
    Narrador con IA:
    - Lee el estado
    - Genera narración coherente
    - Devuelve updates mínimos (memoria)
    """

    llm = get_llm(role="narrator")

    context = {
        "turn": game_state.get("meta", {}).get("turn", 0),
        "player":game_state.get("player", {}),
        "visited_locations": game_state.get("world", {}).get("visited_locations", []),
        "flags": game_state.get("flags", {}),
        "summary": game_state.get("narrative_memory", {}).get("summary", ""),
        "last_events": game_state.get("narrative_memory", {}).get("last_events", [])[-5:],  # últimos 5
        "known_enemies": list(game_state.get("world", {}).get("enemies", {}).keys()),
        "active_quests": game_state.get("world", {}).get("quests", []),
    }

    user_message = f"""
    Estado del juego:
    {json.dumps(context, indent=2, ensure_ascii=False)}
    
    Entrada del jugador:
    {player_input}

    Continúa la historia de forma coherente con el estado.
    """

    from langchain_core.messages import SystemMessage, HumanMessage

    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_message)
    ])
    text = response.content if hasattr(response, "content") else str(response)

    turn = game_state.get("meta", {}).get("turn", 0)
    updates = {
        "narrative_memory": {
            "last_events_append": f"Turno {turn}: jugador -> {player_input} "
        }
    }

    return {"text": text, "updates": updates}