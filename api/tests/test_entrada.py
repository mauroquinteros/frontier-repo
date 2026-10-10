"""Rutas, token y validación de la entrada. Cada caso cita las líneas de experimentos.jsonl."""

import json

import pytest

from app import control
from conftest import TOKEN

E001 = (401, {"error": "E001", "mensaje": "no autorizado"})
E404 = (404, {"error": "E404", "mensaje": "ruta desconocida"})
OK = (200, {"ok": True})
PONG = (200, {"pong": True})


def err(codigo, mensaje, status=400):
    return (status, {"error": codigo, "mensaje": mensaje})


def con_control(m: str) -> str:
    return f"{m};{control.calcular(m)}"


def resp(r):
    return (r.status_code, r.json())


# --- Rutas y token -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "metodo,ruta,token,esperado",
    [
        ("POST", "/msg", None, E001),  # 23, 55
        ("POST", "/msg", "otro", E001),  # 24, 56
        ("GET", "/health", None, E001),  # 25, 57
        ("GET", "/health", "otro", E001),  # 58
        ("POST", "/__reset", None, E001),  # 26, 59
        ("GET", "/health", TOKEN, OK),  # 30, 61
        ("POST", "/__reset", TOKEN, OK),  # 1, 22
        ("GET", "/xyz", TOKEN, E404),  # 46, 62
        ("POST", "/xyz", TOKEN, E404),  # 47
        ("PUT", "/msg", TOKEN, E404),  # 48
        ("DELETE", "/health", TOKEN, E404),  # 63
        ("GET", "/xyz", None, E404),  # 49
        ("GET", "/xyz", "otro", E404),  # 64
        ("GET", "/docs", None, E404),  # supuesto: FastAPI la publica por defecto
        ("GET", "/health/", TOKEN, E404),  # supuesto: sin redirección 307
    ],
)
def test_rutas_y_token(cliente, metodo, ruta, token, esperado):
    headers = {"Authorization": f"Bearer {token}" if token else ""}
    r = cliente.request(metodo, ruta, headers=headers, json={"m": "PING;64"})
    assert resp(r) == esperado


def test_reset_sin_token_no_borra(cliente):
    # 59–60. Por ahora solo comprueba la respuesta; el estado llega con los comandos.
    r = cliente.post("/__reset", headers={"Authorization": ""})
    assert resp(r) == E001


# --- Cuerpo --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "crudo,esperado",
    [
        (b'{"m": "PING;64"', err("E100", "json inválido")),  # 32
        (b'{"m": "PING;64",}', err("E100", "json inválido")),  # 65
        (b"", err("E100", "json inválido")),  # 40, 71
        (b'{"m": NaN}', err("E100", "json inválido")),  # supuesto: NaN no es JSON
        (b"{}", err("E102", "falta m")),  # 33
        (b'{"mensaje": "PING;64"}', err("E102", "falta m")),  # 66
        (b'{"m": 123}', err("E102", "falta m")),  # 35
        (b'{"m": null}', err("E102", "falta m")),  # 36
        (b'{"m": {"a": 1}}', err("E102", "falta m")),  # 68
        (b'["PING;64"]', err("E102", "falta m")),  # 38
        (b'"PING;64"', err("E102", "falta m")),  # 39
        (b"42", err("E102", "falta m")),  # 70
        (b'{"m": "PING;64", "x": 1}', PONG),  # 37
    ],
)
def test_cuerpo(cliente, crudo, esperado):
    assert resp(cliente.post("/msg", content=crudo)) == esperado


def test_content_type_se_ignora(cliente):
    # 41, 72
    r = cliente.post("/msg", content=b'{"m": "PING;64"}', headers={"Content-Type": "text/plain"})
    assert resp(r) == PONG


def _cuerpo(total: int, con_pad: bool) -> bytes:
    """Cuerpo de `total` bytes serializado como lo envía el registrador (ensure_ascii=False)."""
    base = {"m": "PING;64", "pad": ""} if con_pad else {"m": ""}
    falta = total - len(json.dumps(base, ensure_ascii=False).encode())
    if con_pad:
        return json.dumps({"m": "PING;64", "pad": "x" * falta}, ensure_ascii=False).encode()
    return json.dumps({"m": "x" * falta}, ensure_ascii=False).encode()


@pytest.mark.parametrize(
    "total,con_pad,esperado",
    [
        (8192, False, err("E103", "falta control")),  # 84, 90
        (8193, False, err("E101", "cuerpo demasiado grande", 413)),  # 88, 91
        (10009, False, err("E101", "cuerpo demasiado grande", 413)),  # 51
        (8192, True, PONG),  # 92
        (8193, True, err("E101", "cuerpo demasiado grande", 413)),  # 93
    ],
)
def test_tamano(cliente, total, con_pad, esperado):
    cuerpo = _cuerpo(total, con_pad)
    assert len(cuerpo) == total
    assert resp(cliente.post("/msg", content=cuerpo)) == esperado


# --- Segmentos y control -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "m,esperado",
    [
        ("", err("E103", "falta control")),  # 34, 67
        ("PING", err("E103", "falta control")),  # 42
        ("CONSULTA", err("E103", "falta control")),  # 73
        (";;;", err("E104", "segmento vacío")),  # 43
        ("PING;64;", err("E104", "segmento vacío")),  # 44
        ("CONSULTA;;14", err("E104", "segmento vacío")),  # 74
        ("CONSULTA;AC-0001;", err("E104", "segmento vacío")),  # 108
        ("CONSULTA;AC-0001;014", err("E201", "control mal formado")),  # 100
        ("CONSULTA;AC-0001;111", err("E201", "control mal formado")),  # 101
        ("CONSULTA;AC-0001;100", err("E201", "control mal formado")),  # 102
        ("CONSULTA;AC-0001;-1", err("E201", "control mal formado")),  # 104
        ("CONSULTA;AC-0001;+14", err("E201", "control mal formado")),  # 105
        ("CONSULTA;AC-0001; 14", err("E201", "control mal formado")),  # 106
        ("CONSULTA;AC-0001;14 ", err("E201", "control mal formado")),  # 107
        ("CONSULTA;AC-0009;88", err("E202", "control inválido")),  # 95: el control va antes que la cuenta
        ("SALDOS;AC-0001;39", err("E202", "control inválido")),  # 96: y antes que el comando
        ("SALDOS;AC-0001;5X", err("E201", "control mal formado")),  # 97
        ("ALTA;Lucia;Gomez;12", err("E202", "control inválido")),  # 98: y antes que la aridad
        ("PING;64", PONG),  # 29
        ("PING;65", PONG),  # 109: PING no valida el control
        ("PING;0", PONG),  # 110
        ("PING;XX", PONG),  # 111
    ],
)
def test_segmentos_y_control(cliente, m, esperado):
    assert resp(cliente.post("/msg", json={"m": m})) == esperado


def test_control_correcto_pasa_al_comando(cliente):
    # 96 con el control correcto: llega al comando, que es desconocido.
    r = cliente.post("/msg", json={"m": con_control("XYZ;AC-0001")})
    assert resp(r) == err("E301", "comando desconocido ")
