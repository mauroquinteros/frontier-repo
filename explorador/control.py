"""Fórmula del control deducida de los pares del log (ver secuencias/fase2/).

    1. el mensaje sin el control, en mayúsculas;
    2. cada letra pasa a su posición en el alfabeto (A=1 ... Z=26), cada dígito queda igual
       y el resto (';', '-') se descarta;
    3. N = el número que forman esos dígitos concatenados;
    4. control = 98 − (100·N mod 97), siempre entre 2 y 98.

Es ISO 7064 MOD 97-10, el dígito de control del IBAN. Los bordes 97 y 98 se confirmaron con el
buscador (CONSULTA;AC-0038 → 97, CONSULTA;AC-0070 → 98, DEPOSITO;AC-0002;987654 → 98).

Los demás caracteres también se descartan. Probado con í, é, ú, ñ y el espacio (log 480–508:
ALTA;Lucía, José, Raúl, Muñoz, Peña, Iñigo, Ana Maria, Juan Carlos, Luis Miguel). Para otros
caracteres no hay evidencia: `es_seguro` lo indica y el ejecutor usa el buscador.
"""

import string
import unicodedata

CARACTERES_PROBADOS = set(string.ascii_letters + string.digits + ";-" + "íéúñ ")


def valor(texto: str) -> int:
    digitos = []
    for ch in texto.upper():
        if "0" <= ch <= "9":
            digitos.append(ch)
        elif "A" <= ch <= "Z":
            digitos.append(str(ord(ch) - ord("A") + 1))
    return int("".join(digitos) or "0")


def calcular(mensaje: str) -> int:
    """Control del mensaje sin el `;control` final."""
    return 98 - (100 * valor(mensaje)) % 97


def es_seguro(mensaje: str) -> bool:
    return set(mensaje) <= CARACTERES_PROBADOS


def sin_tildes(mensaje: str) -> str:
    """Hipótesis para caracteres sin evidencia: á → a, ñ → n (se quitan las marcas diacríticas)."""
    descompuesto = unicodedata.normalize("NFD", mensaje)
    return "".join(ch for ch in descompuesto if unicodedata.category(ch) != "Mn")
