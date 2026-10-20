from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Mapping, Sequence

from . import exit_code
from .errors import PdiError


def ensure_parent_directory(path: str | Path) -> Path:
    output = Path(path)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise PdiError(
            exit_code.WRITE_ERROR,
            f"Nao foi possivel criar o diretorio de saida: {output.parent}",
        ) from error
    return output


def write_histogram_csv(path: str | Path, histogram: Sequence[int]) -> None:
    """Salva 256 contadores já calculados pelo estudante."""

    if len(histogram) != 256:
        raise ValueError("O histograma deve possuir 256 posicoes.")

    output = ensure_parent_directory(path)
    try:
        with output.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["intensity", "count"])
            for intensity, count in enumerate(histogram):
                writer.writerow([intensity, int(count)])
    except OSError as error:
        raise PdiError(
            exit_code.WRITE_ERROR,
            f"Nao foi possivel criar o CSV: {output}",
        ) from error


def write_json_object(path: str | Path, values: Mapping[str, str]) -> None:
    """Serializa pares texto->texto, como nas variantes C++ e Java."""

    output = ensure_parent_directory(path)
    normalized = {str(key): str(value) for key, value in values.items()}
    try:
        with output.open("w", encoding="utf-8") as file:
            json.dump(normalized, file, ensure_ascii=False, indent=2)
            file.write("\n")
    except OSError as error:
        raise PdiError(
            exit_code.WRITE_ERROR,
            f"Nao foi possivel criar o JSON: {output}",
        ) from error
