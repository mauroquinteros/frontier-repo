"""Único punto de contacto con el servicio antiguo.

Cada request que sale, sin excepción, queda como una línea en experimentos.jsonl
(ver docs/planning.md, sección 5). El log solo crece.
"""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx

from . import config
from .comparar import Texto, respuestas_iguales

SIN_CUERPO = object()
REINTENTOS_RATE_LIMIT = 5
# Observado en todas las corridas de la fase 1 (ej.: log 1, 22, 27).
RESET_OK = (200, {"ok": True})


@dataclass
class Resultado:
    id: int
    seq: str
    status: int
    response: object  # valor JSON, o Texto si no era JSON
    x_req: object
    acerto: bool | None  # None si no había predicción


class Registrador:
    def __init__(self, log: Path = config.LOG, seco: bool = False):
        self.log = Path(log)
        self.seco = seco
        self._token = None if seco else config.token()
        self._cliente = httpx.Client(base_url=config.URL_BASE, timeout=15)
        self._ultimo_envio = 0.0
        self._siguiente_id = self._ultimo_id() + 1

    def _ultimo_id(self) -> int:
        if not self.log.exists():
            return 0
        ultimo = 0
        with self.log.open(encoding="utf-8") as f:
            for linea in f:
                if linea.strip():
                    ultimo = max(ultimo, json.loads(linea)["id"])
        return ultimo

    def enviar_hoy(self) -> int:
        """Requests registrados hoy (hora local), para vigilar el cupo diario."""
        if not self.log.exists():
            return 0
        hoy = datetime.now().strftime("%Y-%m-%d")
        with self.log.open(encoding="utf-8") as f:
            return sum(1 for linea in f if linea.strip() and json.loads(linea)["ts"].startswith(hoy))

    def reset(self, nombre: str, regla: str) -> str:
        """Abre una secuencia nueva con POST /__reset y devuelve su `seq`.

        La `seq` lleva el id del reset (`nombre@id`) para que dos corridas del mismo
        archivo queden como secuencias distintas en el log.
        """
        seq = f"{nombre}@{self._siguiente_id}"
        r = self.enviar(
            seq=seq,
            hipotesis=f'[{regla}] Reset al inicio de la secuencia. Espera 200 {{"ok": true}}',
            ruta="/__reset",
            esperado=RESET_OK,
        )
        if r is not None and not r.acerto:
            raise RuntimeError(f"El reset de {seq} respondió {r.status} {r.response}; se detiene")
        return seq

    def enviar(
        self,
        *,
        seq: str,
        hipotesis: str,
        metodo: str = "POST",
        ruta: str = "/msg",
        cuerpo=SIN_CUERPO,
        crudo: str | None = None,
        content_type: str | None = None,
        auth: str = "valido",
        esperado: tuple[int, object] | None = None,
        conclusion: str | None = None,
    ) -> Resultado | None:
        """Manda un request, lo registra y lo compara con `esperado` si se da.

        `cuerpo` se envía como JSON; `crudo` se envía tal cual (para JSON mal escrito, etc.).
        `auth`: "valido", "ninguno" o "invalido".
        """
        headers = {}
        if auth == "valido":
            headers["Authorization"] = f"Bearer {self._token}"
        elif auth == "invalido":
            headers["Authorization"] = f"Bearer {config.TOKEN_INVALIDO}"
        elif auth != "ninguno":
            raise ValueError(f"auth desconocido: {auth}")

        if cuerpo is not SIN_CUERPO:
            contenido = json.dumps(cuerpo, ensure_ascii=False).encode()
            headers["Content-Type"] = content_type or "application/json"
            request_log = cuerpo
        elif crudo is not None:
            contenido = crudo.encode()
            headers["Content-Type"] = content_type or "application/json"
            request_log = _interpretar(crudo)
        else:
            contenido = None
            if content_type:
                headers["Content-Type"] = content_type
            request_log = None

        hipotesis = _anotar(hipotesis, metodo, ruta, auth, crudo, content_type)

        if self.seco:
            print(f"[seco] {seq} | {metodo} {ruta} | {request_log!r} | {hipotesis}")
            return None

        for _ in range(REINTENTOS_RATE_LIMIT):
            espera = config.INTERVALO_MIN - (time.monotonic() - self._ultimo_envio)
            if espera > 0:
                time.sleep(espera)
            ts = datetime.now().isoformat(timespec="seconds")
            resp = self._cliente.request(metodo, ruta, content=contenido, headers=headers)
            self._ultimo_envio = time.monotonic()

            cuerpo_resp = _interpretar(resp.text)
            x_req = _numero_o_texto(resp.headers.get("X-Req", ""))
            rate_limit = resp.headers.get("X-Frontier-Infra") == "rate-limit"

            acerto = None
            if rate_limit:
                texto_conclusion = "Límite de infraestructura, no es del servicio. Se repite"
            else:
                if esperado is not None:
                    acerto = respuestas_iguales(resp.status_code, cuerpo_resp, *esperado)
                texto_conclusion = conclusion or _conclusion_auto(acerto, resp.status_code, cuerpo_resp)

            resultado = Resultado(self._siguiente_id, seq, resp.status_code, cuerpo_resp, x_req, acerto)
            self._escribir({
                "id": self._siguiente_id,
                "seq": seq,
                "x_req": x_req,
                "ts": ts,
                "hipotesis": hipotesis,
                "request": request_log,
                "status": resp.status_code,
                "response": cuerpo_resp,
                "conclusion": texto_conclusion,
            })
            self._siguiente_id += 1

            if not rate_limit:
                return resultado
            time.sleep(2)
        raise RuntimeError("Rate limit persistente: se detiene la exploración")

    def _escribir(self, linea: dict) -> None:
        with self.log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")


def completar_conclusiones(conclusiones: dict[int, str], log: Path = config.LOG) -> int:
    """Escribe la conclusión de las líneas indicadas por id. Es la única edición que admite el log.

    No pisa una conclusión ya escrita. Devuelve cuántas líneas cambió.
    """
    log = Path(log)
    lineas = log.read_text(encoding="utf-8").splitlines()
    cambiadas = 0
    for i, linea in enumerate(lineas):
        if not linea.strip():
            continue
        d = json.loads(linea)
        if d["id"] in conclusiones and not d.get("conclusion"):
            d["conclusion"] = conclusiones[d["id"]]
            lineas[i] = json.dumps(d, ensure_ascii=False)
            cambiadas += 1
    temporal = log.with_suffix(".tmp")
    temporal.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    temporal.replace(log)
    return cambiadas


def _interpretar(texto: str):
    try:
        return json.loads(texto)
    except ValueError:
        return Texto(texto)


def _numero_o_texto(valor: str):
    return int(valor) if valor.isdigit() else valor


def _anotar(hipotesis, metodo, ruta, auth, crudo, content_type) -> str:
    """Agrega a la hipótesis lo que el log no muestra: ruta, método, token y cuerpo crudo."""
    notas = []
    if (metodo, ruta) != ("POST", "/msg"):
        notas.append(f"{metodo} {ruta}")
    if auth == "ninguno":
        notas.append("sin token")
    elif auth == "invalido":
        notas.append("token inválido")
    if crudo is not None:
        notas.append("cuerpo crudo")
    if content_type and content_type != "application/json":
        notas.append(f"Content-Type: {content_type}")
    return f"{hipotesis} ({'; '.join(notas)})" if notas else hipotesis


def _conclusion_auto(acerto, status, cuerpo) -> str | None:
    if acerto is None:
        return None
    if acerto:
        return "Acertó"
    return f"Falló: respondió {status} {json.dumps(cuerpo, ensure_ascii=False)}"
