"""Compara respuestas con las mismas reglas que el evaluador del reto.

- mismo status;
- si los dos cuerpos son JSON: claves en cualquier orden, arrays en el mismo orden,
  strings y números idénticos;
- si alguno no es JSON: texto exacto.

Los cuerpos llegan ya interpretados: un valor JSON, o un `Texto` si no era JSON.
"""


class Texto(str):
    """Cuerpo de respuesta que no es JSON. Se compara carácter por carácter."""


def _json_igual(a, b) -> bool:
    # bool es subclase de int en Python: true no puede ser igual a 1.
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_json_igual(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_json_igual(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def cuerpos_iguales(a, b) -> bool:
    if isinstance(a, Texto) or isinstance(b, Texto):
        return str(a) == str(b) and isinstance(a, Texto) == isinstance(b, Texto)
    return _json_igual(a, b)


def respuestas_iguales(status_a: int, cuerpo_a, status_b: int, cuerpo_b) -> bool:
    return status_a == status_b and cuerpos_iguales(cuerpo_a, cuerpo_b)
