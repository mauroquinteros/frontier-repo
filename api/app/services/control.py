"""Control de integridad: ISO 7064 MOD 97-10, el dígito de control del IBAN.

Copia de explorador/control.py (solo el cálculo). tests/test_control.py comprueba que ambas den lo
mismo con los pares del log.

    1. el mensaje sin el control, en mayúsculas;
    2. cada letra pasa a su posición en el alfabeto (A=1 ... Z=26), cada dígito queda igual
       y todo lo demás se descarta;
    3. N = el número que forman esos dígitos concatenados;
    4. control = 98 − (100·N mod 97), siempre entre 2 y 98.
"""


def calcular(mensaje: str) -> int:
    """Control del mensaje sin el `;control` final.

    El módulo se calcula dígito a dígito: un mensaje de 8 KB da más de 4.300 dígitos y `int()`
    los rechaza.
    """
    resto = 0
    for ch in mensaje.upper():
        if "0" <= ch <= "9":
            digitos = ch
        elif "A" <= ch <= "Z":
            digitos = str(ord(ch) - ord("A") + 1)
        else:
            continue
        for d in digitos:
            resto = (resto * 10 + int(d)) % 97
    return 98 - (resto * 100) % 97
