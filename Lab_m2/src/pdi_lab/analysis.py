"""M2.2 — componentes conexos, sequencia morfologica e relatorios."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from . import exit_code
from .errors import PdiError
from .image_io import read_image, write_image
from .m2_params import AnalyzeParams, MorphStep
from .result_io import ensure_parent_directory

CSV_HEADER = ["label", "area", "x", "y", "width", "height", "cx", "cy", "kept"]
_SHAPES = {"rect": cv2.MORPH_RECT, "ellipse": cv2.MORPH_ELLIPSE, "cross": cv2.MORPH_CROSS}
_OPS = {
    "open": cv2.MORPH_OPEN,
    "close": cv2.MORPH_CLOSE,
    "erode": cv2.MORPH_ERODE,
    "dilate": cv2.MORPH_DILATE,
}


@dataclass(frozen=True)
class Component:
    label: int
    area: int
    x: int
    y: int
    width: int
    height: int
    cx: float
    cy: float
    kept: bool


def load_binary_mask(path: str) -> np.ndarray:
    mask = read_image(path)
    if mask.ndim != 2 or mask.dtype != np.uint8:
        raise PdiError(
            exit_code.INVALID_PARAMETER,
            "A entrada de 'analyze' deve ser uma mascara de 1 canal e 8 bits "
            "(gere com --operation segment).",
        )
    if not {int(v) for v in np.unique(mask)} <= {0, 255}:
        raise PdiError(
            exit_code.INVALID_PARAMETER,
            "A entrada de 'analyze' nao e binaria: so sao aceitos os valores 0 e 255.",
        )
    return mask


def label_components(
    mask: np.ndarray, connectivity: int, min_area: int
) -> tuple[np.ndarray, list[Component]]:
    """Rotula o primeiro plano (255). O fundo (rotulo 0) nao entra na lista."""
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        (mask > 0).astype(np.uint8), connectivity=connectivity, ltype=cv2.CV_32S
    )
    comps = []
    for i in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[i])
        comps.append(
            Component(i, area, x, y, w, h, float(centroids[i][0]), float(centroids[i][1]),
                      area >= min_area)
        )
    return labels, comps


def write_components_csv(path: str | Path, comps: list[Component]) -> None:
    output = ensure_parent_directory(path)
    try:
        with output.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(CSV_HEADER)
            for c in comps:
                writer.writerow([
                    c.label, c.area, c.x, c.y, c.width, c.height,
                    f"{c.cx:.2f}", f"{c.cy:.2f}", "true" if c.kept else "false",
                ])
    except OSError as error:
        raise PdiError(exit_code.WRITE_ERROR, f"Nao foi possivel criar o CSV: {output}") from error


def apply_step(mask: np.ndarray, step: MorphStep) -> np.ndarray:
    kernel = cv2.getStructuringElement(_SHAPES[step.shape], (step.size, step.size))
    return cv2.morphologyEx(mask, _OPS[step.op], kernel, iterations=step.iterations)


def _summarize(mask: np.ndarray, connectivity: int, min_area: int) -> dict:
    """Contagens e areas de uma mascara, com conectividade 4 e 8 e filtro."""
    h, w = mask.shape
    foreground = int(np.count_nonzero(mask))
    out: dict = {"foreground_pixels": foreground}
    for conn in (4, 8):
        _, comps = label_components(mask, conn, min_area)
        kept = [c for c in comps if c.kept]
        out[f"connectivity_{conn}"] = {
            "components_raw": len(comps),
            "components_kept": len(kept),
            "area_raw_sum": sum(c.area for c in comps),
            "area_kept_sum": sum(c.area for c in kept),
            "touching_border": sum(
                1 for c in comps
                if c.x == 0 or c.y == 0 or c.x + c.width == w or c.y + c.height == h
            ),
        }
        if out[f"connectivity_{conn}"]["area_raw_sum"] != foreground:
            raise PdiError(
                exit_code.GENERAL_ERROR,
                "Inconsistencia: soma das areas dos componentes difere dos pixels de primeiro plano.",
            )
    out["selected"] = out[f"connectivity_{connectivity}"]
    return out


def render_labels(labels: np.ndarray, comps: list[Component]) -> np.ndarray:
    """Imagem colorida: componentes mantidos coloridos e com caixa; descartados em cinza."""
    h, w = labels.shape
    canvas = np.zeros((h, w, 3), np.uint8)
    rng = np.random.default_rng(12)
    for c in comps:
        if c.kept:
            hue = int(rng.integers(0, 180))
            bgr = cv2.cvtColor(np.uint8([[[hue, 200, 255]]]), cv2.COLOR_HSV2BGR)[0, 0]
            canvas[labels == c.label] = bgr
        else:
            canvas[labels == c.label] = (70, 70, 70)
    for c in comps:
        if not c.kept:
            continue
        cv2.rectangle(canvas, (c.x, c.y), (c.x + c.width - 1, c.y + c.height - 1), (255, 255, 255), 1)
        cv2.putText(canvas, str(c.label), (c.x + 2, max(10, c.y - 3)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
    return canvas


def run_analyze(input_path: str, prefix: str, params: AnalyzeParams) -> int:
    initial = load_binary_mask(input_path)
    conn, min_area = params.connectivity, params.min_area

    # Estagio 0: copia da mascara inicial (preservada sem alteracao).
    initial_png = f"{prefix}_initial_mask.png"
    write_image(initial_png, initial)

    labels0, comps0 = label_components(initial, conn, min_area)
    write_components_csv(f"{prefix}_initial.csv", comps0)
    write_image(f"{prefix}_labels_initial.png", render_labels(labels0, comps0))
    initial_summary = _summarize(initial, conn, min_area)

    stages = []
    current = initial
    for index, step in enumerate(params.sequence, start=1):
        current = apply_step(current, step)
        file = f"{prefix}_stage{index}_{step.op}.png"
        write_image(file, current)
        s = _summarize(current, conn, min_area)["selected"]
        stages.append({
            "stage": index,
            **step.as_dict(),
            "file": file,
            "foreground_pixels": int(np.count_nonzero(current)),
            "components_raw": s["components_raw"],
            "components_kept": s["components_kept"],
        })

    final = current
    write_image(f"{prefix}_final_mask.png", final)
    labels1, comps1 = label_components(final, conn, min_area)
    write_components_csv(f"{prefix}_final.csv", comps1)
    write_image(f"{prefix}_labels.png", render_labels(labels1, comps1))
    final_summary = _summarize(final, conn, min_area)

    h, w = initial.shape
    summary = {
        "operation": "analyze",
        "input": str(input_path),
        "image": {"width": w, "height": h},
        "foreground_value": 255,
        "background_value": 0,
        "connectivity": conn,
        "min_area": min_area,
        "area_filter_rule": f"componente mantido se area >= {min_area} pixels",
        "sequence_source": params.sequence_source,
        "sequence": [s.as_dict() for s in params.sequence],
        "initial": initial_summary,
        "final": final_summary,
        "stages": stages,
        "checks": {
            "area_sum_equals_foreground_initial": True,
            "area_sum_equals_foreground_final": True,
        },
        "files": {
            "initial_mask": initial_png,
            "initial_csv": f"{prefix}_initial.csv",
            "final_mask": f"{prefix}_final_mask.png",
            "final_csv": f"{prefix}_final.csv",
            "labels_initial": f"{prefix}_labels_initial.png",
            "labels": f"{prefix}_labels.png",
        },
    }
    out = ensure_parent_directory(f"{prefix}_summary.json")
    try:
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as error:
        raise PdiError(exit_code.WRITE_ERROR, f"Nao foi possivel criar o JSON: {out}") from error

    a, b = initial_summary["selected"], final_summary["selected"]
    print(
        f"analyze connectivity={conn} min_area={min_area} | "
        f"antes: bruto={a['components_raw']} mantido={a['components_kept']} "
        f"area={initial_summary['foreground_pixels']} | "
        f"depois: bruto={b['components_raw']} mantido={b['components_kept']} "
        f"area={final_summary['foreground_pixels']} -> {prefix}_*"
    )
    return exit_code.SUCCESS
