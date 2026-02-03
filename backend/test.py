from utils.almacenamiento import reset_state
from orquestador import handle_turn

if __name__ == "__main__":
    reset_state()
    print("✅ Nueva aventura iniciada (estado reiniciado).")
    while True:
        user = input(">> ").strip()
        if user.lower() in ("salir", "exit", "q"):
            break

        out = handle_turn(user)

        # Imprime de forma robusta aunque cambien las claves
        print("\n--- RESPUESTA ---")
        if isinstance(out, dict):
            print(out.get("text") or out.get("texto_para_jugador") or out.get("respuesta") or str(out))
        else:
            print(str(out))
        print("---------------\n")