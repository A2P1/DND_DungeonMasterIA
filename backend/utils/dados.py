import random


def roll(dice: str) -> int:
    """Tira dados en formato 'NdM' (ej: '1d20', '2d6')."""
    n_str, d_str = dice.lower().split("d")
    n = int(n_str)
    d = int(d_str)
    return sum(random.randint(1, d) for _ in range(n))


def d20() -> int:
    return roll("1d20")


def disadvantage() -> int:
    """Tira 2d20 y se queda con el peor."""
    return min(d20(), d20())


