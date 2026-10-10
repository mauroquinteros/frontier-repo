"""Sondas que no caben en una secuencia fija porque cada request depende del anterior."""

import json

from .control import calcular
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


E303 = (400, {"error": "E303", "mensaje": "monto inválido"})
E401 = (404, {"error": "E401", "mensaje": "cuenta inexistente"})
# Log 517: 250000 se acepta; log 524: 999999999999 da E303.
MONTO_ACEPTADO = 250000
MONTO_RECHAZADO = 999999999999


def _alta(reg: Registrador, seq: str, n: int, regla: str) -> None:
    m = f"ALTA;Sonda{n}"
    reg.enviar(
        seq=seq,
        hipotesis=f'[{regla}] Preparación: ALTA crea AC-{n:04d}. Espera 201 {{"cuentaId": "AC-{n:04d}"}}',
        cuerpo={"m": f"{m};{calcular(m)}"},
        esperado=(201, {"cuentaId": f"AC-{n:04d}"}),
    )


def _deposito(reg: Registrador, seq: str, cuenta: int, monto: int, hipotesis: str, esperado=None):
    m = f"DEPOSITO;AC-{cuenta:04d};{monto}"
    return reg.enviar(seq=seq, hipotesis=hipotesis, cuerpo={"m": f"{m};{calcular(m)}"}, esperado=esperado)


def umbral_monto(reg: Registrador) -> int | None:
    """Busca por bisección el mayor monto que acepta DEPOSITO y lo confirma en otra secuencia.

    Cada intento va sobre una cuenta con saldo 0: tras un depósito aceptado se abre otra cuenta,
    para no confundir un máximo por monto con un máximo de saldo.
    """
    seq = reg.reset("B1-monto-biseccion", "ENT-RESET")
    cuenta = 1
    _alta(reg, seq, cuenta, "COM-DEPOSITO-05")
    bajo, alto = MONTO_ACEPTADO, MONTO_RECHAZADO
    while alto - bajo > 1:
        medio = (bajo + alto) // 2
        r = _deposito(
            reg, seq, cuenta, medio,
            f"[COM-DEPOSITO-05] Depósito de {medio} en una cuenta con saldo 0: "
            "bajo el máximo responde 200; sobre el máximo, 400 E303",
        )
        if r is None:
            return None
        if (r.status, r.response) == E303:
            alto = medio
            completar_conclusiones({r.id: "Sobre el máximo (400 E303)"}, reg.log)
        elif r.status == 200:
            bajo = medio
            completar_conclusiones({r.id: "Bajo el máximo (200)"}, reg.log)
            cuenta += 1
            _alta(reg, seq, cuenta, "COM-DEPOSITO-05")
        else:
            raise RuntimeError(f"Respuesta inesperada en la bisección: {r.status} {r.response}")
        print(f"{medio} → {r.status}")
    print(f"Máximo: acepta {bajo}, rechaza {alto}")

    # Confirmación en otra secuencia: el borde, si el máximo es por depósito o por saldo,
    # y qué gana en TRANSFER entre E303 (monto inválido) y E506 (límite de transferencia).
    seq = reg.reset("B1-monto-borde", "ENT-RESET")
    for n in (1, 2, 3):
        _alta(reg, seq, n, "COM-DEPOSITO-05")
    ok1 = (200, {"status": "recieved", "operacionId": "OP-0001"})
    ok2 = (200, {"status": "recieved", "operacionId": "OP-0002"})
    pruebas = [
        (1, bajo, f"El máximo ({bajo}) se acepta", ok1),
        (2, alto, f"Un peso más ({alto}) da E303", E303),
        (1, 1, "Con el saldo ya en el máximo, depositar 1 se acepta: el máximo es por depósito, no por saldo", ok2),
    ]
    for cuenta, monto, texto, esperado in pruebas:
        status, resp = esperado
        r = _deposito(
            reg, seq, cuenta, monto,
            f"[COM-DEPOSITO-05] {texto}. Espera {status} {json.dumps(resp, ensure_ascii=False)}",
            esperado,
        )
        print(f"{'OK' if r.acerto else 'XX'} #{r.id} {texto} → {r.status} {json.dumps(r.response, ensure_ascii=False)}")

    m = f"TRANSFER;AC-0001;AC-0003;{alto}"
    r = reg.enviar(
        seq=seq,
        hipotesis=f"[ERR-ORDEN-04] Transferir {alto} (sobre el máximo de monto y sobre el límite de transferencia) "
                  'da E303: el monto se valida antes que el límite. Espera 400 {"error": "E303", "mensaje": "monto inválido"}',
        cuerpo={"m": f"{m};{calcular(m)}"},
        esperado=E303,
    )
    print(f"{'OK' if r.acerto else 'XX'} #{r.id} TRANSFER {alto} → {r.status} {json.dumps(r.response, ensure_ascii=False)}")
    return bajo


E506 = (422, {"error": "E506", "mensaje": "límite excedido"})
# Ejemplo 10: 100000 se acepta; ejemplo 9: 120000 da E506.
LIMITE_ACEPTADO = 100000
LIMITE_RECHAZADO = 120000


def _transfer(reg: Registrador, seq: str, origen: int, destino: int, monto: int, hipotesis: str, esperado=None):
    m = f"TRANSFER;AC-{origen:04d};AC-{destino:04d};{monto}"
    return reg.enviar(seq=seq, hipotesis=hipotesis, cuerpo={"m": f"{m};{calcular(m)}"}, esperado=esperado)


def umbral_transferencia(reg: Registrador) -> int | None:
    """Busca por bisección el mayor monto que acepta TRANSFER y confirma el borde en otra secuencia.

    El límite es por operación (B2-acumulado, log 607–618), así que todas las transferencias
    salen de la misma cuenta, con saldo de sobra. Tras cada E506 se intercala una transferencia
    de 1 para que la cuenta no se bloquee.
    """
    seq = reg.reset("B2-limite-biseccion", "ENT-RESET")
    _alta(reg, seq, 1, "COM-TRANSFER-01")
    _alta(reg, seq, 2, "COM-TRANSFER-01")
    _deposito(reg, seq, 1, MONTO_RECHAZADO // 100,
              "[COM-TRANSFER-01] Preparación: saldo de sobra en AC-0001. "
              'Espera 200 {"status": "recieved", "operacionId": "OP-0001"}',
              (200, {"status": "recieved", "operacionId": "OP-0001"}))
    bajo, alto = LIMITE_ACEPTADO, LIMITE_RECHAZADO
    while alto - bajo > 1:
        medio = (bajo + alto) // 2
        r = _transfer(reg, seq, 1, 2, medio,
                      f"[COM-TRANSFER-01] Transferir {medio} con saldo de sobra: "
                      "bajo el límite responde 200; sobre el límite, 422 E506")
        if r is None:
            return None
        if (r.status, r.response) == E506:
            alto = medio
            completar_conclusiones({r.id: "Sobre el límite (422 E506)"}, reg.log)
            # 3 E506 seguidos bloquean la cuenta (E510, log 626 y 634); un éxito reinicia el
            # contador (log 647–649).
            reinicio = _transfer(reg, seq, 1, 2, 1,
                                 "[MEM-BLOQUEO-03] Transferencia de 1 para reiniciar el contador de E506 seguidos: "
                                 "responde 200")
            if reinicio.status != 200:
                raise RuntimeError(f"El reinicio del contador falló: {reinicio.status} {reinicio.response}")
            completar_conclusiones({reinicio.id: "Reinicio del contador (200)"}, reg.log)
        elif r.status == 200:
            bajo = medio
            completar_conclusiones({r.id: "Bajo el límite (200)"}, reg.log)
        else:
            raise RuntimeError(f"Respuesta inesperada en la bisección: {r.status} {r.response}")
        print(f"{medio} → {r.status}")
    print(f"Límite: acepta {bajo}, rechaza {alto}")

    seq = reg.reset("B2-limite-borde", "ENT-RESET")
    _alta(reg, seq, 1, "COM-TRANSFER-01")
    _alta(reg, seq, 2, "COM-TRANSFER-01")
    _deposito(reg, seq, 1, 500000,
              "[COM-TRANSFER-01] Preparación: 500000 en AC-0001. "
              'Espera 200 {"status": "recieved", "operacionId": "OP-0001"}',
              (200, {"status": "recieved", "operacionId": "OP-0001"}))
    pruebas = [
        (alto, f"Un peso sobre el límite ({alto}) da E506", E506),
        (bajo, f"El límite exacto ({bajo}) se acepta", (200, {"status": "recieved", "operacionId": "OP-0002"})),
    ]
    for monto, texto, esperado in pruebas:
        status, resp = esperado
        r = _transfer(reg, seq, 1, 2, monto,
                      f"[COM-TRANSFER-01] {texto}. Espera {status} {json.dumps(resp, ensure_ascii=False)}",
                      esperado)
        print(f"{'OK' if r.acerto else 'XX'} #{r.id} {texto} → {r.status} {json.dumps(r.response, ensure_ascii=False)}")
    return bajo
