"""Estado en memoria del único proceso (el set le habla a un solo proceso)."""


class Estado:
    def __init__(self) -> None:
        self.reiniciar()

    def reiniciar(self) -> None:
        pass


_estado = Estado()


def get_estado() -> Estado:
    return _estado
