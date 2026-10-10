"""Ejecuta secuencias definidas en YAML: reset y luego cada paso en orden.

Formato de un archivo (ver secuencias/README.md):

    seq: T2-limite-acumulado
    pasos:
      - regla: COM-TRANSFER-04
        hipotesis: Dos transferencias de 80000 pasan si el límite es por operación
        m: "TRANSFER;AC-0001;AC-0002;80000;{c}"
        espera: {status: 200, response: {status: recieved, operacionId: OP-0002}}
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .buscador import Buscador
from .comparar import Texto
from .control import calcular, es_seguro
from .registrador import SIN_CUERPO, Registrador

MARCA_CONTROL = ";{c}"
CLAVES_PASO = {"regla", "hipotesis", "m", "cuerpo", "crudo", "metodo", "ruta", "auth", "content_type", "espera"}


@dataclass
class Paso:
    regla: str
    hipotesis: str
    metodo: str = "POST"
    ruta: str = "/msg"
    m: str | None = None
    cuerpo: object = SIN_CUERPO
    crudo: str | None = None
    auth: str = "valido"
    content_type: str | None = None
    esperado: tuple[int, object] | None = None


@dataclass
class Secuencia:
    nombre: str
    archivo: Path
    pasos: list[Paso] = field(default_factory=list)
    reset: bool = True


def cargar(archivo: Path) -> Secuencia:
    datos = yaml.safe_load(Path(archivo).read_text(encoding="utf-8"))
    sec = Secuencia(nombre=datos["seq"], archivo=Path(archivo), reset=datos.get("reset", True))
    for i, p in enumerate(datos["pasos"], 1):
        if extra := set(p) - CLAVES_PASO:
            raise ValueError(f"{archivo}, paso {i}: claves desconocidas {sorted(extra)}")
        if not p.get("regla") or not p.get("hipotesis"):
            raise ValueError(f"{archivo}, paso {i}: faltan 'regla' o 'hipotesis'")
        paso = Paso(
            regla=p["regla"],
            hipotesis=p["hipotesis"],
            metodo=p.get("metodo", "POST"),
            ruta=p.get("ruta", "/msg"),
            m=p.get("m"),
            cuerpo=p.get("cuerpo", SIN_CUERPO),
            crudo=p.get("crudo"),
            auth=p.get("auth", "valido"),
            content_type=p.get("content_type"),
        )
        if "espera" in p:
            e = p["espera"]
            cuerpo = Texto(e["texto"]) if "texto" in e else e["response"]
            paso.esperado = (e["status"], cuerpo)
        sec.pasos.append(paso)
    return sec


def _con_control(m: str) -> str | None:
    """Si el mensaje termina en ;{c}, devuelve el mensaje sin el control."""
    return m[: -len(MARCA_CONTROL)] if m.endswith(MARCA_CONTROL) else None


def ejecutar(sec: Secuencia, reg: Registrador, buscador: Buscador) -> tuple[int, int]:
    """Corre la secuencia y devuelve (aciertos, predicciones)."""
    # {c} se calcula con la fórmula. Si el mensaje tiene caracteres sin evidencia (tildes,
    # espacios), se busca antes, en su propia secuencia, para no mezclar los intentos con
    # el estado de esta.
    bases = [b for p in sec.pasos if p.m and (b := _con_control(p.m))]
    controles = {b: calcular(b) for b in bases if es_seguro(b)}
    if dudosos := [b for b in bases if not es_seguro(b)]:
        controles |= buscador.resolver(dudosos)
    if faltan := [b for b, c in controles.items() if c is None and not reg.seco]:
        print(f"{sec.archivo}: sin control para {faltan}; no se ejecuta")
        return 0, 0

    print(f"\n== {sec.nombre} ({sec.archivo})")
    seq = reg.reset(sec.nombre, "ENT-RESET") if sec.reset else sec.nombre
    aciertos = predicciones = 0
    for p in sec.pasos:
        cuerpo = p.cuerpo
        if p.m is not None:
            base = _con_control(p.m)
            m = f"{base};{controles.get(base, '?')}" if base is not None else p.m
            cuerpo = {"m": m}

        hipotesis = f"[{p.regla}] {p.hipotesis}"
        if p.esperado:
            status, esperado = p.esperado
            hipotesis += f". Espera {status} {json.dumps(esperado, ensure_ascii=False)}"

        r = reg.enviar(
            seq=seq,
            hipotesis=hipotesis,
            metodo=p.metodo,
            ruta=p.ruta,
            cuerpo=cuerpo,
            crudo=p.crudo,
            content_type=p.content_type,
            auth=p.auth,
            esperado=p.esperado,
        )
        if r is None:
            continue
        marca = {True: "OK ", False: "XX ", None: " · "}[r.acerto]
        print(f"{marca}#{r.id} [{p.regla}] {r.status} {json.dumps(r.response, ensure_ascii=False)}")
        if r.acerto is not None:
            predicciones += 1
            aciertos += r.acerto
    return aciertos, predicciones
