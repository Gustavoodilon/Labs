from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import exit_code
from .errors import PdiError


def _invalid_kernel(message: str) -> PdiError:
    return PdiError(exit_code.INVALID_PARAMETER, message)


@dataclass(frozen=True)
class Kernel:
    """Kernel quadrado de dimensão ímpar já validado pela infraestrutura."""

    size: int
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if self.size <= 0 or self.size % 2 == 0:
            raise _invalid_kernel("O kernel deve ter dimensao impar e maior que zero.")
        if len(self.values) != self.size * self.size:
            raise _invalid_kernel("Quantidade de coeficientes invalida para o kernel.")

    @property
    def radius(self) -> int:
        return self.size // 2

    def at(self, row: int, col: int) -> float:
        if row < 0 or col < 0 or row >= self.size or col >= self.size:
            raise IndexError("Indice fora dos limites do kernel.")
        return self.values[row * self.size + col]


def read_kernel(path: str | Path) -> Kernel:
    """Lê o arquivo; aplicar a convolução continua sendo tarefa do estudante."""

    input_path = Path(path)
    try:
        lines = input_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise PdiError(
            exit_code.READ_ERROR,
            f"Nao foi possivel abrir o kernel: {input_path}",
        ) from error

    rows: list[list[float]] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rows.append([float(token) for token in line.split()])
        except ValueError as error:
            raise _invalid_kernel(f"Coeficiente invalido no kernel: {line}") from error

    if not rows:
        raise _invalid_kernel("O arquivo de kernel esta vazio.")

    size = len(rows[0])
    if size == 0 or len(rows) != size or size % 2 == 0:
        raise _invalid_kernel("O kernel deve ser quadrado e possuir dimensao impar.")
    if any(len(row) != size for row in rows):
        raise _invalid_kernel("Todas as linhas do kernel devem ter o mesmo tamanho.")

    values = tuple(value for row in rows for value in row)
    return Kernel(size=size, values=values)
