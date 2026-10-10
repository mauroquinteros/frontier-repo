"""Sondas que no caben en una secuencia fija porque cada request depende del anterior."""

import json

from .registrador import Registrador, completar_conclusiones

E101 = (413, {"error": "E101", "mensaje": "cuerpo demasiado grande"})
E103 = (400, {"error": "E103", "mensaje": "falta control"})
PONG = (200, {"pong": True})
# Log 51: un cuerpo de 10.009 bytes ya da E101.
MAXIMO_CONOCIDO = 10009


def _bytes(cuerpo) -> int:
    # Mismo serializado que usa el registrador al enviar.
    return len(json.dumps(cuerpo, ensure_ascii=False).encode())


def _cuerpo_m(total: int) -> dict:
    """Cuerpo {"m": "xxx..."} de `total` bytes. Sin ';' el servicio responde E103."""
    return {"m": "x" * (total - _bytes({"m": ""}))}


def _cuerpo_relleno(total: int) -> dict:
    """PING válido más un campo extra que lleva el cuerpo a `total` bytes."""
    base = {"m": "PING;64", "pad": ""}
    return {"m": "PING;64", "pad": "x" * (total - _bytes(base))}


def umbral_cuerpo(reg: Registrador) -> int | None:
    """Busca por bisección el mayor cuerpo aceptado y lo verifica en otra secuencia.

    Devuelve ese tamaño en bytes.
    """
    seq = reg.reset("F1-tamano-biseccion", "ENT-RESET")
    bajo, alto = _bytes({"m": ""}), MAXIMO_CONOCIDO
    while alto - bajo > 1:
        medio = (bajo + alto) // 2
        r = reg.enviar(
            seq=seq,
            hipotesis=f"[ENT-CUERPO-08] Cuerpo de {medio} bytes: bajo el límite da 400 E103; sobre el límite, 413 E101",
            cuerpo=_cuerpo_m(medio),
        )
        if r is None:
            return None
        if (r.status, r.response) == E101:
            alto = medio
            completar_conclusiones({r.id: "Sobre el límite (413 E101)"}, reg.log)
        elif (r.status, r.response) == E103:
            bajo = medio
            completar_conclusiones({r.id: "Bajo el límite (400 E103)"}, reg.log)
        else:
            raise RuntimeError(f"Respuesta inesperada en la bisección: {r.status} {r.response}")
        print(f"{medio} bytes → {r.status}")

    print(f"Límite: acepta {bajo} bytes, rechaza {alto}")
    # Segunda secuencia: confirma el borde y si cuenta el cuerpo entero o solo `m`.
    seq = reg.reset("F1-tamano-borde", "ENT-RESET")
    pruebas = [
        (f"El cuerpo más grande aceptado ({bajo} bytes) da E103", _cuerpo_m(bajo), E103),
        (f"Un byte más ({alto}) da E101", _cuerpo_m(alto), E101),
        (f"Con m corto y un campo extra, {bajo} bytes en total responde pong", _cuerpo_relleno(bajo), PONG),
        (f"Con m corto y un campo extra, {alto} bytes en total da E101: el límite es del cuerpo entero",
         _cuerpo_relleno(alto), E101),
    ]
    for texto, cuerpo, esperado in pruebas:
        status, resp = esperado
        r = reg.enviar(
            seq=seq,
            hipotesis=f"[ENT-CUERPO-08] {texto}. Espera {status} {json.dumps(resp, ensure_ascii=False)}",
            cuerpo=cuerpo,
            esperado=esperado,
        )
        print(f"{'OK' if r.acerto else 'XX'} #{r.id} {texto} → {r.status} {json.dumps(r.response, ensure_ascii=False)}")
    return bajo
