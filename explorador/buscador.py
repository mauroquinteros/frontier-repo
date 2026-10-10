"""Encuentra el control válido de un mensaje probando 0..99 contra el servicio.

Sirve mientras no conozcamos la fórmula. Cada par mensaje → control queda en
controles.json, que es la entrada del deductor de fórmula.

Un control se da por bueno cuando la respuesta deja de ser E202 y, además, el
control siguiente vuelve a dar E202. Esa segunda prueba evita un falso positivo
si el servicio rechaza el mensaje por otra razón antes de mirar el control
(por ejemplo, una cuenta inexistente).
"""

import json
from pathlib import Path

from . import config
from .control import calcular
from .registrador import Registrador

ESPERADO_E202 = (400, {"error": "E202", "mensaje": "control inválido"})


def es_e202(status: int, cuerpo) -> bool:
    return status == 400 and isinstance(cuerpo, dict) and cuerpo.get("error") == "E202"


class Buscador:
    def __init__(self, registrador: Registrador, cache: Path = config.CACHE_CONTROLES):
        self.reg = registrador
        self.cache_path = Path(cache)
        self.cache: dict[str, int] = (
            json.loads(self.cache_path.read_text(encoding="utf-8")) if self.cache_path.exists() else {}
        )

    def _guardar(self) -> None:
        self.cache_path.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def resolver(self, mensajes: list[str]) -> dict[str, int | None]:
        """Devuelve el control de cada mensaje (sin el `;control` final).

        Los que no están en caché se buscan en una sola secuencia que empieza con reset.
        None si no se pudo determinar.
        """
        pendientes = [m for m in dict.fromkeys(mensajes) if m not in self.cache]
        if pendientes and not self.reg.seco:
            seq = self.reg.reset("BUSCA", "INT-BUSCA")
            for mensaje in pendientes:
                control = self._buscar(seq, mensaje)
                if control is not None:
                    self.cache[mensaje] = control
                    self._guardar()
        elif pendientes:
            for mensaje in pendientes:
                print(f"[seco] buscaría el control de {mensaje!r} (hasta 101 requests)")
        return {m: self.cache.get(m) for m in mensajes}

    def _buscar(self, seq: str, mensaje: str) -> int | None:
        # La predicción de la fórmula va primero: si acierta, cuesta 2 requests en vez de ~51.
        prediccion = calcular(mensaje)
        for c in [prediccion] + [c for c in range(100) if c != prediccion]:
            r = self._probar(seq, mensaje, c)
            if es_e202(r.status, r.response):
                continue
            verificacion = self._probar(seq, mensaje, (c + 1) % 100)
            if es_e202(verificacion.status, verificacion.response):
                print(f"control de {mensaje!r} = {c}")
                return c
            print(f"{mensaje!r}: {c} y {(c + 1) % 100} no dan E202; el control no decide la respuesta")
            return None
        print(f"{mensaje!r}: los 100 controles dan E202")
        return None

    def _probar(self, seq: str, mensaje: str, c: int):
        return self.reg.enviar(
            seq=seq,
            hipotesis=f"[INT-BUSCA] Si {c} no es el control de {mensaje!r}, responde 400 E202",
            cuerpo={"m": f"{mensaje};{c}"},
            esperado=ESPERADO_E202,
        )
