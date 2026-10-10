"""Comandos, con las reglas vigentes desde el cambio de las 15:30.

Orden en TRANSFER (log 704–707, 796–803, 812–815):
    aridad (E302) → monto (E303) → misma cuenta (E304) → cuenta (E401) → bloqueada (E510)
    → límite (E506) → saldo (E507)
"""

import re

from fastapi.responses import JSONResponse

from app.core.respuestas import PONG, RECIBIDA, YA_ANULADA, ErrorServicio, ok
from app.services.estado import Estado, Operacion

ARIDAD = {"ALTA": 1, "CONSULTA": 1, "DEPOSITO": 2, "TRANSFER": 3, "ANULA": 1, "PING": None, "HALT": 1}
# En un empate de la sugerencia gana el primero en orden alfabético (HALTA → ALTA, HANG y PILT →
# HALT; log 832, 1346–1347).
CANDIDATOS_SUGERENCIA = sorted(ARIDAD)
DISTANCIA_SUGERENCIA = 2  # 2 sugiere, 3 no (log 825–828)

MONTO = re.compile(r"[1-9][0-9]*")  # sin ceros a la izquierda, signo ni decimales (log 518–524)
MONTO_MAXIMO = 9_999_999_999  # log 602–606
# Desde las 15:30: 50000 se acepta y 50001 da E506 (log 922/924, 958/959). Antes era 100000.
LIMITE_TRANSFERENCIA = 50_000
RECHAZOS_PARA_BLOQUEO = 3


def ejecutar(partes: list[str], estado: Estado) -> JSONResponse:
    comando, args = partes[0], partes[1:]
    if comando == "PING":
        return ok(PONG)
    if comando not in ARIDAD:
        sugerencia = _sugerencia(comando)
        raise ErrorServicio("E301", **({"sugerencia": sugerencia} if sugerencia else {}))
    if len(args) != ARIDAD[comando]:
        raise ErrorServicio("E302")
    return COMANDOS[comando](estado, *args)


def _halt(estado: Estado, argumento: str) -> JSONResponse:
    # Con cualquier argumento pide confirmación y no cambia nada; el argumento no se valida como
    # cuenta (log 1310–1319, 1407). Sin argumentos o con 4: E302 (830, 1309). Supuesto: 2 y 3
    # argumentos también dan E302; la forma de confirmar no se probó.
    raise ErrorServicio("E520")


def _alta(estado: Estado, nombre: str) -> JSONResponse:
    return ok({"cuentaId": estado.nueva_cuenta(nombre)}, 201)


def _consulta(estado: Estado, cuenta_id: str) -> JSONResponse:
    cuenta = _cuenta(estado, cuenta_id)
    # "cuenta_id" aquí y "cuentaId" en ALTA, como el original.
    return ok({"cuenta_id": cuenta_id, "saldo": _formato_saldo(cuenta.saldo)})


def _deposito(estado: Estado, cuenta_id: str, monto: str) -> JSONResponse:
    valor = _monto(monto)  # E303 antes que E401 (log 1344–1345)
    cuenta = _cuenta(estado, cuenta_id)
    cuenta.saldo += valor
    if cuenta.bloqueada:
        # Un depósito en la propia cuenta la desbloquea y reinicia sus contadores: al volver a
        # bloquearse, "intentos" empieza en 1 (log 1335–1336, 1355–1357, 1396–1401).
        cuenta.bloqueada, cuenta.rechazos, cuenta.intentos = False, 0, 0
    return _recibida(estado.nueva_operacion(Operacion(valor, cuenta_id)))


def _transfer(estado: Estado, origen_id: str, destino_id: str, monto: str) -> JSONResponse:
    valor = _monto(monto)
    if origen_id == destino_id:
        raise ErrorServicio("E304")
    origen = _cuenta(estado, origen_id)
    destino = _cuenta(estado, destino_id)
    if origen.bloqueada:
        # E303 y E401 en una cuenta bloqueada no suben "intentos" (log 1200–1201).
        origen.intentos += 1
        raise ErrorServicio("E510", intentos=origen.intentos)
    # Solo E506 y E507 suman al contador; E303, E304 y E401 no lo tocan (log 757–791).
    rechazo = "E506" if valor > LIMITE_TRANSFERENCIA else "E507" if valor > origen.saldo else None
    if rechazo:
        origen.rechazos += 1
        if origen.rechazos >= RECHAZOS_PARA_BLOQUEO:
            origen.bloqueada = True
        raise ErrorServicio(rechazo)
    origen.rechazos = 0  # solo un éxito reinicia el contador (log 647–649)
    origen.saldo -= valor
    destino.saldo += valor
    return _recibida(estado.nueva_operacion(Operacion(valor, destino_id, origen_id)))


def _anula(estado: Estado, op_id: str) -> JSONResponse:
    operacion = estado.operaciones.get(op_id)  # distingue mayúsculas: op-0001 → E402 (log 737)
    if operacion is None:
        raise ErrorServicio("E402")
    if operacion.anulada:
        return ok(YA_ANULADA)  # fallo con status 200, como el original
    operacion.anulada = True
    # Revierte aunque el destino quede en negativo (log 731–733).
    estado.cuentas[operacion.destino].saldo -= operacion.monto
    if operacion.origen is not None:
        estado.cuentas[operacion.origen].saldo += operacion.monto
    return ok({"ok": True, "anulada": op_id})


COMANDOS = {
    "ALTA": _alta,
    "CONSULTA": _consulta,
    "DEPOSITO": _deposito,
    "TRANSFER": _transfer,
    "ANULA": _anula,
    "HALT": _halt,
}


def _cuenta(estado: Estado, cuenta_id: str):
    cuenta = estado.cuentas.get(cuenta_id)  # distingue mayúsculas: ac-0001 → E401 (log 540)
    if cuenta is None:
        raise ErrorServicio("E401")
    return cuenta


def _monto(texto: str) -> int:
    if not MONTO.fullmatch(texto) or int(texto) > MONTO_MAXIMO:
        raise ErrorServicio("E303")
    return int(texto)


def _recibida(op_id: str) -> JSONResponse:
    return ok({"status": RECIBIDA, "operacionId": op_id})


def _formato_saldo(centavos: int) -> str:
    # Negativo tras ANULA: "-400.00" (log 1121).
    signo = "-" if centavos < 0 else ""
    return f"{signo}{abs(centavos) // 100}.{abs(centavos) % 100:02d}"


def _sugerencia(comando: str) -> str | None:
    mejor, distancia = None, DISTANCIA_SUGERENCIA + 1
    for candidato in CANDIDATOS_SUGERENCIA:
        d = _levenshtein(comando, candidato)
        if d < distancia:
            mejor, distancia = candidato, d
    return mejor


def _levenshtein(a: str, b: str) -> int:
    fila = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        anterior, fila[0] = fila[0], i
        for j, cb in enumerate(b, 1):
            anterior, fila[j] = fila[j], min(fila[j] + 1, fila[j - 1] + 1, anterior + (ca != cb))
    return fila[-1]
