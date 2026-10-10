"""Compara la última corrida de cada secuencia antes de un corte con la última después.

Sirve para detectar cambios del servicio durante el día (sección CAM). Solo lee el log.

Los pasos se emparejan por regla + request + anotación (método, ruta, token, cuerpo crudo), y
no por posición ni por el texto completo de la hipótesis: el formato de la hipótesis del reset
cambió entre corridas. Si el mismo paso se repite (tres TRANSFER iguales), se empareja por orden
de aparición.

Solo se comparan secuencias que existen como YAML en secuencias/. Las bisecciones de las sondas
(`*-biseccion`, `*-borde`) y el buscador (`BUSCA`) eligen los requests según las respuestas, así
que no se pueden emparejar: los bordes se comparan volviendo a correr las sondas.
"""

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from . import config
from .comparar import respuestas_iguales
from .registrador import _interpretar

SECUENCIAS = Path(__file__).resolve().parent.parent / "secuencias"
# Lo que `_anotar` agrega al final de la hipótesis.
ANOTACION = re.compile(
    r"\(((?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) [^()]*|sin token[^()]*|token inválido[^()]*"
    r"|cuerpo crudo[^()]*|Content-Type[^()]*)\)$"
)
REGLA = re.compile(r"^\[([^\]]+)\]")
RATE_LIMIT = "Límite de infraestructura"


@dataclass
class Corrida:
    seq: str
    ts: str
    lineas: list[dict] = field(default_factory=list)


def nombres_yaml(directorio: Path = SECUENCIAS) -> set[str]:
    nombres = set()
    for archivo in directorio.rglob("*.yaml"):
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
        if isinstance(datos, dict) and "seq" in datos:
            nombres.add(datos["seq"])
    return nombres


def leer_corridas(log: Path) -> dict[str, list[Corrida]]:
    """Agrupa el log por `seq` (`nombre@id`) y devuelve las corridas de cada nombre, en orden."""
    por_seq: dict[str, Corrida] = {}
    with Path(log).open(encoding="utf-8") as f:
        for linea in f:
            if not linea.strip():
                continue
            d = json.loads(linea)
            corrida = por_seq.setdefault(d["seq"], Corrida(d["seq"], d["ts"]))
            corrida.lineas.append(d)
    corridas: dict[str, list[Corrida]] = defaultdict(list)
    for corrida in por_seq.values():
        corridas[corrida.seq.partition("@")[0]].append(corrida)
    return corridas


def clave(linea: dict) -> tuple:
    hipotesis = linea.get("hipotesis") or ""
    regla = REGLA.match(hipotesis)
    anotacion = ANOTACION.search(hipotesis)
    request = json.dumps(linea.get("request"), ensure_ascii=False, sort_keys=True)
    return (regla.group(1) if regla else "", request, anotacion.group(1) if anotacion else "")


def _con_ocurrencia(lineas: list[dict]) -> dict[tuple, dict]:
    vistos: Counter = Counter()
    resultado = {}
    for linea in lineas:
        if (linea.get("conclusion") or "").startswith(RATE_LIMIT):
            continue
        k = clave(linea)
        resultado[k + (vistos[k],)] = linea
        vistos[k] += 1
    return resultado


def _respuesta(linea: dict):
    # El log guarda el texto que no era JSON como string; se reinterpreta igual que al registrar.
    cuerpo = linea["response"]
    if isinstance(cuerpo, str):
        cuerpo = _interpretar(cuerpo)
    return linea["status"], cuerpo


def _mostrar(linea: dict) -> str:
    return f"#{linea['id']}  {linea['status']} {json.dumps(linea['response'], ensure_ascii=False)}"


def _paso(linea: dict) -> str:
    k = clave(linea)
    request = linea.get("request")
    texto = request.get("m") if isinstance(request, dict) and isinstance(request.get("m"), str) else k[1]
    return f"[{k[0]}] {texto}" + (f"  ({k[2]})" if k[2] else "")


def comparar(antes: Corrida, ahora: Corrida) -> tuple[list[tuple[dict, dict]], int, list[dict], list[dict]]:
    """Devuelve (distintas, iguales, sin par en antes, sin par en ahora). `distintas` va en orden de ahora."""
    viejo = _con_ocurrencia(antes.lineas)
    nuevo = _con_ocurrencia(ahora.lineas)
    distintas, iguales = [], 0
    for k, linea in nuevo.items():
        if k not in viejo:
            continue
        if respuestas_iguales(*_respuesta(linea), *_respuesta(viejo[k])):
            iguales += 1
        else:
            distintas.append((viejo[k], linea))
    sin_par_antes = [l for k, l in viejo.items() if k not in nuevo]
    sin_par_ahora = [l for k, l in nuevo.items() if k not in viejo]
    return distintas, iguales, sin_par_antes, sin_par_ahora


def interpretar_corte(texto: str) -> str:
    """`15:30` → hoy a esa hora; también acepta una fecha y hora ISO. Devuelve el formato de `ts`."""
    if re.fullmatch(r"\d{1,2}:\d{2}", texto):
        h, m = texto.split(":")
        return datetime.now().replace(hour=int(h), minute=int(m), second=0).isoformat(timespec="seconds")
    return datetime.fromisoformat(texto).isoformat(timespec="seconds")


def informe(corte: str, log: Path = config.LOG, detalle: bool = False) -> int:
    """Imprime las diferencias y devuelve cuántas secuencias cambiaron."""
    corte = interpretar_corte(corte)
    yaml_ok = nombres_yaml()
    corridas = leer_corridas(log)
    print(f"Corte: {corte}. Antes = última corrida previa al corte; ahora = última posterior.\n")

    cambiadas = 0
    total_iguales = total_distintas = 0
    pendientes, sin_previa, excluidas = [], [], []
    for nombre in sorted(corridas, key=lambda n: corridas[n][0].lineas[0]["id"]):
        if nombre not in yaml_ok:
            excluidas.append(nombre)
            continue
        previas = [c for c in corridas[nombre] if c.ts < corte]
        nuevas = [c for c in corridas[nombre] if c.ts >= corte]
        if not nuevas:
            pendientes.append(nombre)
            continue
        if not previas:
            sin_previa.append(nombre)
            continue
        antes, ahora = previas[-1], nuevas[-1]
        distintas, iguales, sin_antes, sin_ahora = comparar(antes, ahora)
        total_iguales += iguales
        total_distintas += len(distintas)
        marca = "≠" if distintas else "="
        extra = f" · {len(sin_antes) + len(sin_ahora)} sin par" if sin_antes or sin_ahora else ""
        print(f"{marca} {nombre}  {antes.seq} → {ahora.seq}  {iguales} iguales · {len(distintas)} distintas{extra}")
        if distintas:
            cambiadas += 1
            mostrar = distintas if detalle else distintas[:1]
            for i, (viejo, nuevo) in enumerate(mostrar):
                titulo = "PRIMERA" if i == 0 else "después"
                print(f"    {titulo}: {_paso(nuevo)}")
                print(f"      antes {_mostrar(viejo)}")
                print(f"      ahora {_mostrar(nuevo)}")
            if not detalle and len(distintas) > 1:
                print(f"    … {len(distintas) - 1} más (pueden ser consecuencia de la primera; ver --detalle)")
        if detalle:
            for linea in sin_antes:
                print(f"    sin par (solo antes): {_paso(linea)}  #{linea['id']}")
            for linea in sin_ahora:
                print(f"    sin par (solo ahora): {_paso(linea)}  #{linea['id']}")

    print(f"\nResumen: {total_iguales} iguales · {total_distintas} distintas · "
          f"{cambiadas} secuencias con cambios")
    if pendientes:
        print(f"Sin corrida después del corte ({len(pendientes)}): {', '.join(pendientes)}")
    if sin_previa:
        print(f"Sin corrida antes del corte ({len(sin_previa)}): {', '.join(sin_previa)}")
    if excluidas:
        print(f"Excluidas (sondas y buscador, no tienen YAML): {', '.join(excluidas)}")
    return cambiadas
