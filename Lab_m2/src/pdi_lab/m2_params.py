"""Parametros e validacoes especificos da M2 (operacoes `segment` e `analyze`).

As funcoes levantam:
- `MissingArgument` quando falta um argumento exigido (codigo 2);
- `ValueError` quando o valor e invalido (codigo 5);
- `FileNotFoundError` quando um arquivo de configuracao nao existe (codigo 3).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .cli import CliOptions
from .parameters import has_parameter, parameter_as_int

SEGMENT_METHODS = ("fixed", "otsu", "adaptive", "hsv")
MORPH_OPS = ("erode", "dilate", "open", "close")
MORPH_SHAPES = ("rect", "ellipse", "cross")
LOSSLESS_EXTENSIONS = {".png", ".bmp", ".tif", ".tiff"}

DEFAULT_CONNECTIVITY = 8
DEFAULT_MIN_AREA = 0
DEFAULT_BLOCK_SIZE = 31
DEFAULT_C = 10
DEFAULT_MORPH = "open:ellipse:3:1,close:ellipse:5:1"


class MissingArgument(Exception):
    """Argumento obrigatorio ausente."""


@dataclass(frozen=True)
class SegmentParams:
    method: str
    threshold: int | None = None
    invert: bool = False
    blur: int = 0
    block_size: int = DEFAULT_BLOCK_SIZE
    c: int = DEFAULT_C
    hsv_lower: tuple[int, int, int] | None = None
    hsv_upper: tuple[int, int, int] | None = None

    def as_dict(self) -> dict:
        data = {"method": self.method, "invert": self.invert, "blur": self.blur}
        if self.method == "fixed":
            data["threshold"] = self.threshold
        elif self.method == "adaptive":
            data["block_size"] = self.block_size
            data["c"] = self.c
        elif self.method == "hsv":
            data["hsv_lower"] = list(self.hsv_lower)
            data["hsv_upper"] = list(self.hsv_upper)
        return data


@dataclass(frozen=True)
class MorphStep:
    op: str
    shape: str
    size: int
    iterations: int

    def as_dict(self) -> dict:
        return {
            "op": self.op,
            "shape": self.shape,
            "size": self.size,
            "iterations": self.iterations,
        }


@dataclass(frozen=True)
class AnalyzeParams:
    connectivity: int
    min_area: int
    sequence: tuple[MorphStep, ...]
    sequence_source: str


def _bool(options: CliOptions, name: str, default: bool) -> bool:
    if not has_parameter(options, name):
        return default
    text = options.parameters[name].strip().lower()
    if text in {"true", "1", "yes", "sim"}:
        return True
    if text in {"false", "0", "no", "nao"}:
        return False
    raise ValueError(f"Valor invalido para --{name}: {text}. Use true ou false.")


def _hsv_triplet(options: CliOptions, name: str) -> tuple[int, int, int]:
    if not has_parameter(options, name):
        raise MissingArgument(f"O metodo hsv exige --{name.replace('_', '-')}.")
    text = options.parameters[name]
    flag = f"--{name.replace('_', '-')}"
    parts = text.split(",")
    if len(parts) != 3:
        raise ValueError(f"{flag} deve ter o formato H,S,V (ex.: 0,0,0): {text}")
    try:
        h, s, v = (int(p) for p in parts)
    except ValueError as error:
        raise ValueError(f"{flag} deve conter tres inteiros: {text}") from error
    if not 0 <= h <= 179:
        raise ValueError(f"{flag}: H deve estar entre 0 e 179 (escala do OpenCV).")
    if not (0 <= s <= 255 and 0 <= v <= 255):
        raise ValueError(f"{flag}: S e V devem estar entre 0 e 255.")
    return h, s, v


def segment_params(options: CliOptions) -> SegmentParams:
    if not has_parameter(options, "method"):
        raise MissingArgument("A operacao 'segment' exige --method.")
    method = options.parameters["method"]
    if method not in SEGMENT_METHODS:
        raise ValueError(
            f"Metodo desconhecido: {method}. Use {', '.join(SEGMENT_METHODS)}."
        )

    invert = _bool(options, "invert", False)
    blur = parameter_as_int(options, "blur") if has_parameter(options, "blur") else 0
    if blur < 0 or (blur > 1 and blur % 2 == 0):
        raise ValueError("--blur deve ser 0 (sem suavizacao) ou um inteiro impar >= 3.")
    if blur == 1:
        blur = 0

    threshold = None
    block_size = DEFAULT_BLOCK_SIZE
    c = DEFAULT_C
    lower = upper = None

    if method == "fixed":
        if not has_parameter(options, "threshold"):
            raise MissingArgument("O metodo fixed exige --threshold.")
        threshold = parameter_as_int(options, "threshold")
        if not 0 <= threshold <= 255:
            raise ValueError("--threshold deve estar entre 0 e 255.")
    elif method == "adaptive":
        if has_parameter(options, "block_size"):
            block_size = parameter_as_int(options, "block_size")
        if block_size < 3 or block_size % 2 == 0:
            raise ValueError("--block-size deve ser um inteiro impar >= 3.")
        if has_parameter(options, "c"):
            c = parameter_as_int(options, "c")
    elif method == "hsv":
        lower = _hsv_triplet(options, "hsv_lower")
        upper = _hsv_triplet(options, "hsv_upper")

    return SegmentParams(
        method=method,
        threshold=threshold,
        invert=invert,
        blur=blur,
        block_size=block_size,
        c=c,
        hsv_lower=lower,
        hsv_upper=upper,
    )


def validate_output_is_lossless(path: str) -> None:
    suffix = Path(path).suffix.lower()
    if suffix not in LOSSLESS_EXTENSIONS:
        raise ValueError(
            f"A mascara deve ser salva em formato sem perdas "
            f"({', '.join(sorted(LOSSLESS_EXTENSIONS))}); recebido '{suffix}'."
        )


def _build_step(op: str, shape: str, size, iterations) -> MorphStep:
    if op not in MORPH_OPS:
        raise ValueError(f"Operacao morfologica desconhecida: {op}. Use {', '.join(MORPH_OPS)}.")
    if shape not in MORPH_SHAPES:
        raise ValueError(f"Forma de elemento estruturante desconhecida: {shape}. Use {', '.join(MORPH_SHAPES)}.")
    try:
        size = int(size)
        iterations = int(iterations)
    except (TypeError, ValueError) as error:
        raise ValueError("Tamanho e iteracoes do passo morfologico devem ser inteiros.") from error
    if size < 3 or size % 2 == 0:
        raise ValueError("O tamanho do elemento estruturante deve ser impar e >= 3.")
    if iterations < 1:
        raise ValueError("O numero de iteracoes deve ser >= 1.")
    return MorphStep(op, shape, size, iterations)


def parse_morph_spec(spec: str) -> tuple[MorphStep, ...]:
    steps = []
    for chunk in spec.split(","):
        parts = chunk.strip().split(":")
        if len(parts) != 4:
            raise ValueError(
                f"Passo morfologico invalido '{chunk}'. Use operacao:forma:tamanho:iteracoes."
            )
        steps.append(_build_step(*parts))
    return tuple(steps)


def load_morph_config(path: Path) -> tuple[MorphStep, ...]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data["sequence"]
        return tuple(
            _build_step(i["op"], i.get("shape", "ellipse"), i["size"], i.get("iterations", 1))
            for i in items
        )
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as error:
        raise ValueError(f"Arquivo de configuracao morfologica invalido: {path} ({error})") from error


def _check_sequence(steps: tuple[MorphStep, ...]) -> None:
    if len(steps) < 2:
        raise ValueError("A sequencia morfologica deve ter ao menos duas operacoes.")
    if not any(s.op in {"open", "close"} for s in steps):
        raise ValueError("A sequencia deve incluir abertura (open) ou fechamento (close).")
    for before, after in zip(steps, steps[1:]):
        if before == after:
            raise ValueError(
                f"Passos consecutivos identicos ({before.op}:{before.shape}:"
                f"{before.size}:{before.iterations}) nao formam uma sequencia."
            )


def analyze_params(options: CliOptions) -> AnalyzeParams:
    connectivity = DEFAULT_CONNECTIVITY
    if has_parameter(options, "connectivity"):
        connectivity = parameter_as_int(options, "connectivity")
        if connectivity not in {4, 8}:
            raise ValueError("--connectivity deve ser 4 ou 8.")

    min_area = DEFAULT_MIN_AREA
    if has_parameter(options, "min_area"):
        min_area = parameter_as_int(options, "min_area")
        if min_area < 0:
            raise ValueError("--min-area deve ser um inteiro nao negativo.")

    if has_parameter(options, "morph") and has_parameter(options, "morph_config"):
        raise ValueError("Use --morph ou --morph-config, nao os dois.")

    if has_parameter(options, "morph_config"):
        path = Path(options.parameters["morph_config"])
        if not path.is_file():
            raise FileNotFoundError(f"Nao foi possivel abrir a configuracao: {path}")
        steps, source = load_morph_config(path), f"arquivo:{path.name}"
    elif has_parameter(options, "morph"):
        steps, source = parse_morph_spec(options.parameters["morph"]), "argumento"
    else:
        steps, source = parse_morph_spec(DEFAULT_MORPH), "padrao"

    _check_sequence(steps)
    return AnalyzeParams(connectivity, min_area, steps, source)
