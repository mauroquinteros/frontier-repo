"""Estado en memoria del único proceso (el set le habla a un solo proceso).

Los montos se guardan en centavos, como enteros: desde las 15:30 CONSULTA muestra 40000 como
"400.00" (log 841).
"""

from dataclasses import dataclass, field


@dataclass
class Cuenta:
    nombre: str
    saldo: int = 0
    # E506/E507 seguidos como origen de TRANSFER; con 3 la cuenta queda bloqueada (log 634, 715).
    rechazos: int = 0
    bloqueada: bool = False
    # Desde las 15:30, E510 lleva "intentos": cuántos E510 lleva la cuenta, desde 1 (log 1199–1203).
    intentos: int = 0


@dataclass
class Operacion:
    monto: int
    destino: str
    origen: str | None = None  # None en un depósito
    anulada: bool = False


@dataclass
class Estado:
    cuentas: dict[str, Cuenta] = field(default_factory=dict)
    operaciones: dict[str, Operacion] = field(default_factory=dict)

    def reiniciar(self) -> None:
        self.cuentas.clear()
        self.operaciones.clear()

    def nueva_cuenta(self, nombre: str) -> str:
        cuenta_id = f"AC-{len(self.cuentas) + 1:04d}"
        self.cuentas[cuenta_id] = Cuenta(nombre)
        return cuenta_id

    def nueva_operacion(self, operacion: Operacion) -> str:
        # Los rechazos y ANULA no consumen número (ejemplos 2–3, 13–18; log 636).
        op_id = f"OP-{len(self.operaciones) + 1:04d}"
        self.operaciones[op_id] = operacion
        return op_id


_estado = Estado()


def get_estado() -> Estado:
    return _estado
