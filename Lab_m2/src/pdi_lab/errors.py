from __future__ import annotations


class PdiError(RuntimeError):
    """Erro de infraestrutura associado a um código de saída padronizado."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
