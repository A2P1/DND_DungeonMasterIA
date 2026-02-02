import random

def roll(dice: str) -> int:
    """
    Soporta formato tipo '1d20', '2d6', '1d8'.

    """
    n_str, d_str = dice.lower().split('d')
    n = int(n_str)
    d = int(d_str)
    total = sum(random.randint(1, d) for _ in range(n))
    return total

def d20() -> int:
    """Tira un dado de 20 caras."""
    return roll('1d20')

