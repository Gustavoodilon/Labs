"""M2.1 — geracao de mascara binaria (objeto = 255, fundo = 0)."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from . import exit_code
from .errors import PdiError
from .image_io import read_image, write_image
from .m2_params import SegmentParams
from .result_io import ensure_parent_directory


def to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        gray = image
    elif image.shape[2] == 4:
        gray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    else:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if gray.dtype != np.uint8:
        raise PdiError(exit_code.INVALID_PARAMETER, "Somente imagens de 8 bits sao suportadas.")
    return gray


def _to_bgr(image: np.ndarray) -> np.ndarray:
    if image.ndim == 3 and image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image


def segment_mask(image: np.ndarray, params: SegmentParams) -> tuple[np.ndarray, dict]:
    """Retorna (mascara uint8 {0,255}, informacoes extras como limiar de Otsu)."""
    info: dict = {}
    kind = cv2.THRESH_BINARY_INV if params.invert else cv2.THRESH_BINARY

    if params.method == "hsv":
        bgr = _to_bgr(image)
        if bgr.ndim != 3:
            raise PdiError(
                exit_code.INVALID_PARAMETER,
                "O metodo hsv exige imagem colorida (3 canais).",
            )
        if params.blur:
            bgr = cv2.GaussianBlur(bgr, (params.blur, params.blur), 0)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        (lh, ls, lv), (uh, us, uv) = params.hsv_lower, params.hsv_upper
        if lh <= uh:
            mask = cv2.inRange(hsv, (lh, ls, lv), (uh, us, uv))
        else:
            # Faixa que cruza a descontinuidade do matiz (ex.: vermelho 170..10).
            low = cv2.inRange(hsv, (lh, ls, lv), (179, us, uv))
            high = cv2.inRange(hsv, (0, ls, lv), (uh, us, uv))
            mask = cv2.bitwise_or(low, high)
            info["hue_wraparound"] = True
        if params.invert:
            mask = cv2.bitwise_not(mask)
        return mask, info

    gray = to_gray(image)
    if params.blur:
        gray = cv2.GaussianBlur(gray, (params.blur, params.blur), 0)

    if params.method == "fixed":
        _, mask = cv2.threshold(gray, params.threshold, 255, kind)
    elif params.method == "otsu":
        used, mask = cv2.threshold(gray, 0, 255, kind | cv2.THRESH_OTSU)
        info["otsu_threshold"] = float(used)
    elif params.method == "adaptive":
        mask = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, kind, params.block_size, params.c
        )
    else:  # pragma: no cover - validado antes
        raise PdiError(exit_code.INVALID_PARAMETER, f"Metodo desconhecido: {params.method}")
    return mask, info


def check_binary_mask(mask: np.ndarray, expected_shape: tuple[int, int]) -> dict:
    """Confirma programaticamente: 1 canal, mesmas dimensoes, valores em {0, 255}."""
    values = {int(v) for v in np.unique(mask)}
    checks = {
        "single_channel": mask.ndim == 2,
        "same_size_as_input": tuple(mask.shape[:2]) == tuple(expected_shape),
        "dtype_uint8": mask.dtype == np.uint8,
        "values_only_0_255": values <= {0, 255},
        "values_present": sorted(values),
    }
    checks["ok"] = all(v for k, v in checks.items() if k != "values_present")
    return checks


def run_segment(input_path: str, output_path: str, params: SegmentParams) -> int:
    image = read_image(input_path)
    mask, info = segment_mask(image, params)

    write_image(output_path, mask)

    # Relê o arquivo salvo: a validação vale para o que está em disco.
    saved = cv2.imread(output_path, cv2.IMREAD_UNCHANGED)
    if saved is None:
        raise PdiError(exit_code.WRITE_ERROR, f"Nao foi possivel reler a mascara: {output_path}")
    checks = check_binary_mask(saved, image.shape[:2])
    if not checks["ok"]:
        raise PdiError(exit_code.GENERAL_ERROR, f"Mascara de saida invalida: {checks}")

    total = int(saved.size)
    foreground = int(np.count_nonzero(saved))
    report = {
        "input": str(input_path),
        "output": str(output_path),
        "width": int(saved.shape[1]),
        "height": int(saved.shape[0]),
        "parameters": params.as_dict(),
        "info": info,
        "foreground_pixels": foreground,
        "total_pixels": total,
        "foreground_ratio": foreground / total,
        "checks": checks,
    }
    sidecar = ensure_parent_directory(Path(output_path).with_suffix(".json"))
    sidecar.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"segment method={params.method} foreground={foreground}/{total} "
        f"({100.0 * foreground / total:.2f}%) binary=OK -> {output_path}"
    )
    return exit_code.SUCCESS
