from __future__ import annotations

from enum import Enum
from pathlib import Path

from .cli import CliOptions


class BorderStrategy(Enum):
    """Estratégias de borda previstas no Laboratório M1.3."""

    COPY = "copy"
    REPLICATE = "replicate"


def has_parameter(options: CliOptions, name: str) -> bool:
    value = options.parameters.get(name)
    return value is not None and value != ""


def _require(options: CliOptions, name: str) -> str:
    value = options.parameters.get(name)
    if value is None or value == "":
        raise ValueError(f"Parametro ausente: --{name}")
    return value


def parameter_as_int(options: CliOptions, name: str) -> int:
    text = _require(options, name)
    try:
        return int(text)
    except ValueError as error:
        raise ValueError(f"Valor invalido para --{name}: {text}") from error


def parameter_as_float(options: CliOptions, name: str) -> float:
    text = _require(options, name)
    try:
        return float(text)
    except ValueError as error:
        raise ValueError(f"Valor invalido para --{name}: {text}") from error


def parameter_as_path(options: CliOptions, name: str) -> Path:
    return Path(_require(options, name))


def parameter_as_border(options: CliOptions, name: str = "border") -> BorderStrategy:
    text = _require(options, name)
    try:
        return BorderStrategy(text)
    except ValueError as error:
        raise ValueError(
            f"Valor invalido para --{name}: {text}. Use copy ou replicate."
        ) from error
