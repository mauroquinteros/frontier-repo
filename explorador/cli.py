"""CLI de exploración.

    uv run explorador correr secuencias/fase0/*.yaml [--seco]
    uv run explorador buscar "DEPOSITO;AC-0001;300000" [--seco]
    uv run explorador cupo
    uv run explorador sonda-tamano
    uv run explorador sonda-monto
    uv run explorador sonda-limite [--bajo 50000 --alto 87654]
    uv run explorador concluir 25 "texto de la conclusión"
    uv run explorador diferencias 15:30 [--detalle]
"""

import argparse
from pathlib import Path

from . import config
from .buscador import Buscador
from .diferencias import informe
from .ejecutor import cargar, ejecutar
from .registrador import Registrador, completar_conclusiones
from .sondas import umbral_cuerpo, umbral_monto, umbral_transferencia

AVISO_CUPO = 0.9


def main() -> None:
    parser = argparse.ArgumentParser(prog="explorador")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_correr = sub.add_parser("correr", help="ejecuta secuencias YAML")
    p_correr.add_argument("archivos", nargs="+", type=Path)
    p_correr.add_argument("--seco", action="store_true", help="muestra lo que mandaría, sin enviar ni registrar")

    p_buscar = sub.add_parser("buscar", help="busca el control de mensajes (sin el ;control final)")
    p_buscar.add_argument("mensajes", nargs="+")
    p_buscar.add_argument("--seco", action="store_true")

    sub.add_parser("cupo", help="requests registrados hoy frente al cupo diario")
    sub.add_parser("sonda-tamano", help="bisección del límite de tamaño del cuerpo (E101)")
    sub.add_parser("sonda-monto", help="bisección del monto máximo de DEPOSITO (E303)")
    p_limite = sub.add_parser("sonda-limite", help="bisección del límite por operación de TRANSFER (E506)")
    p_limite.add_argument("--bajo", type=int, help="monto ya visto como aceptado")
    p_limite.add_argument("--alto", type=int, help="monto ya visto como rechazado (E506)")

    p_concluir = sub.add_parser("concluir", help="completa la conclusión vacía de una línea del log")
    p_concluir.add_argument("id", type=int)
    p_concluir.add_argument("texto")

    p_dif = sub.add_parser("diferencias", help="compara cada secuencia antes y después de un corte (solo lee el log)")
    p_dif.add_argument("corte", help="hora de hoy (15:30) o fecha y hora ISO")
    p_dif.add_argument("--detalle", action="store_true", help="todas las diferencias y los pasos sin par")

    args = parser.parse_args()
    if args.comando == "concluir":
        n = completar_conclusiones({args.id: args.texto})
        print("Conclusión escrita" if n else "Sin cambios: el id no existe o ya tenía conclusión")
        return
    if args.comando == "diferencias":
        informe(args.corte, detalle=args.detalle)
        return

    reg = Registrador(seco=getattr(args, "seco", False))
    _avisar_cupo(reg)

    if args.comando == "correr":
        # Se cargan todos antes de enviar nada: un error de formato no deja corridas a medias.
        secuencias = [cargar(a) for a in args.archivos]
        buscador = Buscador(reg)
        total_ok = total = 0
        for sec in secuencias:
            ok, n = ejecutar(sec, reg, buscador)
            total_ok += ok
            total += n
        if total:
            print(f"\nPredicciones acertadas: {total_ok}/{total} ({100 * total_ok / total:.0f} %)")
    elif args.comando == "buscar":
        for mensaje, control in Buscador(reg).resolver(args.mensajes).items():
            print(f"{mensaje};{control}")
    elif args.comando == "sonda-tamano":
        umbral_cuerpo(reg)
    elif args.comando == "sonda-monto":
        umbral_monto(reg)
    elif args.comando == "sonda-limite":
        bordes = {k: v for k, v in (("bajo", args.bajo), ("alto", args.alto)) if v is not None}
        umbral_transferencia(reg, **bordes)


def _avisar_cupo(reg: Registrador) -> None:
    usados = reg.enviar_hoy()
    print(f"Cupo de hoy: {usados}/{config.CUPO_DIARIO}")
    if usados >= config.CUPO_DIARIO * AVISO_CUPO:
        print("AVISO: más del 90 % del cupo diario usado")
