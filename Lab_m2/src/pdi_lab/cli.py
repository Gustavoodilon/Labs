from __future__ import annotations

import argparse
from dataclasses import dataclass, field


@dataclass
class CliOptions:
    """Representação comum dos argumentos recebidos pela aplicação."""

    operation: str | None = None
    input: str | None = None
    output: str | None = None
    version: bool = False
    parameters: dict[str, str] = field(default_factory=dict)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdi_lab",
        description="Projeto pdi_lab de Processamento de Imagens (base M1 + M2.1 segment + M2.2 analyze)",
    )
    parser.add_argument("--version", action="store_true")

    # As três linguagens expõem os mesmos nomes de parâmetros.
    for name in [
        "operation",
        "input",
        "output",
        "value",
        "levels",
        "threshold",
        "alpha",
        "kernel",
        "border",
        "size",
        # M2.1 — segmentacao
        "method",
        "invert",
        "blur",
        "block-size",
        "c",
        "hsv-lower",
        "hsv-upper",
        # M2.2 — analise (conectividade, filtro por area, sequencia morfologica)
        "connectivity",
        "min-area",
        "morph",
        "morph-config",
    ]:
        parser.add_argument(f"--{name}")

    return parser


def parse_cli(argv=None) -> CliOptions:
    values = vars(build_parser().parse_args(argv))
    version = bool(values.pop("version"))
    operation = values.pop("operation")
    input_path = values.pop("input")
    output_path = values.pop("output")
    parameters = {name: value for name, value in values.items() if value is not None}

    return CliOptions(
        operation=operation,
        input=input_path,
        output=output_path,
        version=version,
        parameters=parameters,
    )


def version_requested(options: CliOptions) -> bool:
    return options.version
