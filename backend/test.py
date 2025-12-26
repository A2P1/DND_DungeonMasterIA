from orquestador import handle_turn

if __name__ == "__main__":
    while True:
        user = input(">> ")
        if user.lower() in ("salir", "exit", "q"):
            break
        out = handle_turn(user)
        print("\n" + out["text"] + "\n")