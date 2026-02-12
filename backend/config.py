import os
from dotenv import load_dotenv

load_dotenv() # Carga las variables desde .env (la api_key)

#Función para comprobar que la variable de entorno está definida
def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Falta la variable de entorno '{name}'. "
            f"Revisa tu archivo .env y asegúrate de tenerla definida"
        )
    return value

def get_llm(role: str = "narrator"):
    """
        Devuelve un LLM de OpenAI para el rol indicado.
        Puedes configurar modelos por rol con variables de entorno opcionales:
            - OPENAI_MODEL_NARRATOR
            - OPENAI_MODEL_COMBAT
    """

    from langchain_openai import ChatOpenAI

    api_key = _require_env("OPENAI_API_KEY")

    model_env = {
        "narrator": "OPENAI_MODEL_NARRATOR",
        "combat": "OPENAI_MODEL_COMBAT",
    }.get(role, "OPENAI_MODEL_NARRATOR")

    model = os.getenv(model_env, "gpt-4o-mini").strip()

    temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.8"))

    return ChatOpenAI(
        openai_api_key=api_key,
        model=model,
        temperature=temperature,
        timeout=30,
        #response_format = {"type": "json_schema"}
    )

    