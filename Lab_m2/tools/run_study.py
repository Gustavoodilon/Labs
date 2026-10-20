"""Reproduz o estudo da M2.1 e da M2.2 com as imagens do template do professor.

Uso (a partir da pasta python/, com o ambiente virtual ativo):
    python tools/run_study.py

Imagens usadas (todas em images/input/, fornecidas pelo professor no template):
- m1_shapes_border_256.png : favoravel (formas claras sobre fundo escuro, objetos na borda,
                             uma linha fina que liga formas);
- m1_gray_scene_256.png    : dificil (gradiente de iluminacao, formas de baixo contraste);
- m1_checkerboard_256.png  : caso extra, so para comparar conectividade 4 e 8.

Todas as operacoes sao chamadas pela mesma CLI documentada no README
(pdi_lab.__main__.main), para provar a reprodutibilidade.

Nao ha mascara de referencia independente. Unica excecao: em m1_shapes_border_256 cada
elemento tem um nivel de cinza proprio (85, 130, 170, 210, 235 sobre fundo 30), o que
permite medir a cobertura de cada elemento (origem: valores de pixel da propria imagem).
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pdi_lab.__main__ import main as pdi_main  # noqa: E402
from pdi_lab.analysis import label_components  # noqa: E402
from pdi_lab.m2_params import SegmentParams  # noqa: E402
from pdi_lab.segmentation import segment_mask  # noqa: E402

SHAPES = "m1_shapes_border_256"
SCENE = "m1_gray_scene_256"
BOARD = "m1_checkerboard_256"

# Elementos de m1_shapes_border_256, identificados pelo nivel de cinza de cada um.
SHAPE_LEVELS = {85: "quadrado inferior", 130: "quadrado superior direito", 170: "linha diagonal",
                210: "retangulo superior esquerdo", 235: "circulo"}

CONFIGS = {
    SHAPES: {
        "fixed": ["--method", "fixed", "--threshold", "60"],
        "otsu": ["--method", "otsu"],
        "adaptive": ["--method", "adaptive", "--block-size", "101", "--c=-5"],
    },
    SCENE: {
        "fixed": ["--method", "fixed", "--threshold", "200"],
        "otsu": ["--method", "otsu"],
        "adaptive": ["--method", "adaptive", "--block-size", "101", "--c=-20"],
        # tentativa de segmentar as formas ESCURAS (polaridade oposta): documenta a falha
        "adaptive_dark": ["--method", "adaptive", "--block-size", "101", "--c", "3", "--invert", "true"],
    },
    BOARD: {
        "fixed": ["--method", "fixed", "--threshold", "128"],
    },
}
WORKING = {SHAPES: "fixed", SCENE: "adaptive", BOARD: "fixed"}
# Contagem manual por inspecao visual (origem documentada no REPORT.md).
MANUAL_COUNT = {SHAPES: 5, SCENE: 5, BOARD: 128}

MORPH = "open:ellipse:5:1,close:ellipse:7:1"
MORPH_REVERSED = "close:ellipse:7:1,open:ellipse:5:1"
MORPH_BIG_CLOSE = "open:ellipse:5:1,close:ellipse:61:1"
CONNECTIVITY = 8
MIN_AREA = 20

OUT = ROOT / "images" / "output"
RES = ROOT / "results"


def run(args: list[str]) -> None:
    code = pdi_main(args)
    if code != 0:
        raise SystemExit(f"Comando falhou ({code}): {' '.join(args)}")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def read(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    assert img is not None, path
    return img


def comps(mask: np.ndarray, conn: int = 8, min_area: int = 0):
    return label_components(mask, conn, min_area)[1]


def level_coverage(mask: np.ndarray, image: np.ndarray) -> dict:
    """Fracao dos pixels de cada elemento de SHAPES que esta marcada na mascara."""
    m = mask > 0
    cov = {name: float(np.count_nonzero(m & (image == lv)) / np.count_nonzero(image == lv))
           for lv, name in SHAPE_LEVELS.items()}
    cov["fundo marcado (fp, px)"] = int(np.count_nonzero(m & (image == 30)))
    return cov


def caption(img: np.ndarray, text: str) -> np.ndarray:
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    bar = np.full((22, img.shape[1], 3), 30, np.uint8)
    cv2.putText(bar, text, (4, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
    return np.vstack([bar, img])


def panel(tiles: list[tuple[np.ndarray, str]]) -> np.ndarray:
    return np.hstack([caption(t, c) for t, c in tiles])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    RES.mkdir(parents=True, exist_ok=True)
    study: dict = {"m2_1": {}, "m2_2": {}, "sensitivity": []}
    md: list[str] = []

    # ---------------- M2.1 ----------------
    md.append("## M2.1 — proporção de primeiro plano e componentes (conectividade 8, sem filtro)\n")
    md.append("| Imagem | Configuração | Parâmetros | 1º plano (px) | Proporção | Componentes | Maior componente (px) |")
    md.append("|---|---|---|---:|---:|---:|---:|")
    masks: dict[tuple[str, str], np.ndarray] = {}
    for name, cfgs in CONFIGS.items():
        src = ROOT / "images/input" / f"{name}.png"
        gray = read(src)
        study["m2_1"][name] = {}
        for cfg, extra in cfgs.items():
            out = OUT / f"{name}_{cfg}_mask.png"
            run(["--operation", "segment", "--input", rel(src), "--output", rel(out)] + extra)
            mask = read(out)
            masks[(name, cfg)] = mask
            side = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
            cc = comps(mask)
            entry = {**side["parameters"], **side["info"], "foreground_pixels": side["foreground_pixels"],
                     "foreground_ratio": side["foreground_ratio"], "components_8": len(cc),
                     "largest_component": max((c.area for c in cc), default=0), "command_args": extra}
            if name == SHAPES:
                entry["coverage"] = level_coverage(mask, gray)
            study["m2_1"][name][cfg] = entry
            params = ", ".join(f"{k}={v}" for k, v in side["parameters"].items() if k != "method")
            if "otsu_threshold" in side["info"]:
                params += f", limiar calculado={side['info']['otsu_threshold']:.0f}"
            md.append(f"| {name} | {cfg} | {side['parameters']['method']}: {params} | {side['foreground_pixels']} | "
                      f"{100 * side['foreground_ratio']:.2f}% | {len(cc)} | {entry['largest_component']} |")

    md.append("\n## M2.1 — cobertura por elemento em m1_shapes_border_256 (fração dos pixels de cada elemento marcada)\n")
    md.append("| Configuração | " + " | ".join(SHAPE_LEVELS.values()) + " | Fundo marcado (px) |")
    md.append("|---|" + "---:|" * (len(SHAPE_LEVELS) + 1))
    for cfg in CONFIGS[SHAPES]:
        cov = study["m2_1"][SHAPES][cfg]["coverage"]
        md.append(f"| {cfg} | " + " | ".join(f"{100 * cov[n]:.0f}%" for n in SHAPE_LEVELS.values())
                  + f" | {cov['fundo marcado (fp, px)']} |")

    # Figuras M2.1
    a = read(ROOT / "images/input" / f"{SHAPES}.png")
    err = cv2.cvtColor((a * 0.5).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    wm, ref = masks[(SHAPES, WORKING[SHAPES])] > 0, a > 30
    err[wm & ref] = (80, 200, 80)
    err[wm & ~ref] = (0, 0, 255)
    err[~wm & ref] = (255, 120, 0)
    cv2.imwrite(str(RES / f"fig_m2_1_{SHAPES}.png"), panel([
        (a, "original"),
        (masks[(SHAPES, "fixed")], "fixed T=60"),
        (masks[(SHAPES, "otsu")], "otsu"),
        (masks[(SHAPES, "adaptive")], "adaptive 101 C=-5"),
        (err, "fixed: verde=ok azul=FN"),
    ]))
    b = read(ROOT / "images/input" / f"{SCENE}.png")
    cv2.imwrite(str(RES / f"fig_m2_1_{SCENE}.png"), panel([
        (b, "original"),
        (masks[(SCENE, "fixed")], "fixed T=200 (claro)"),
        (masks[(SCENE, "otsu")], "otsu"),
        (masks[(SCENE, "adaptive")], "adaptive 101 C=-20 (claro)"),
        (masks[(SCENE, "adaptive_dark")], "adaptive 101 C=3 inv (escuro)"),
    ]))

    # ---------------- Sensibilidade ----------------
    rows = []
    for name, sweeps in (
        (SHAPES, [("fixed", f"T={t}", SegmentParams("fixed", threshold=t))
                  for t in (20, 40, 60, 84, 85, 100, 130, 170, 210)]
         + [("adaptive", f"block={bs},C=-5", SegmentParams("adaptive", block_size=bs, c=-5))
            for bs in (31, 51, 101, 151)]),
        (SCENE, [("fixed", f"T={t}", SegmentParams("fixed", threshold=t))
                 for t in (100, 150, 180, 200, 215, 230)]
         + [("adaptive", f"block={bs},C=-20", SegmentParams("adaptive", block_size=bs, c=-20))
            for bs in (31, 51, 101, 151)]
         + [("adaptive", f"block=101,C={c}", SegmentParams("adaptive", block_size=101, c=c))
            for c in (-10, -20, -30, -40)]),
    ):
        gray = read(ROOT / "images/input" / f"{name}.png")
        for method, label, p in sweeps:
            mask, _ = segment_mask(gray, p)
            cc = comps(mask)
            row = {"image": name, "method": method, "param": label,
                   "foreground_ratio": round(float(np.count_nonzero(mask) / mask.size), 4),
                   "components_8": len(cc), "largest_component": max((c.area for c in cc), default=0)}
            if name == SHAPES:
                cov = level_coverage(mask, gray)
                row["elements_ge_50pct"] = sum(cov[n] >= 0.5 for n in SHAPE_LEVELS.values())
            rows.append(row)
    fields = ["image", "method", "param", "foreground_ratio", "components_8", "largest_component", "elements_ge_50pct"]
    with (RES / "m2_1_sensibilidade.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in fields} for r in rows)
    study["sensitivity"] = rows

    # ---------------- M2.2 ----------------
    runs = {}
    for name in (SHAPES, SCENE, BOARD):
        mask_in = OUT / f"{name}_{WORKING[name]}_mask.png"
        prefix = RES / name
        run(["--operation", "analyze", "--input", rel(mask_in), "--output", rel(prefix),
             "--connectivity", str(CONNECTIVITY), "--min-area", str(MIN_AREA), "--morph", MORPH])
        summ = json.loads((RES / f"{name}_summary.json").read_text(encoding="utf-8"))
        extra = {}
        if name != BOARD:
            for tag, spec in (("ordem_inversa", MORPH_REVERSED), ("fechamento61", MORPH_BIG_CLOSE)):
                pre = RES / f"{name}_{tag}"
                run(["--operation", "analyze", "--input", rel(mask_in), "--output", rel(pre),
                     "--connectivity", str(CONNECTIVITY), "--min-area", str(MIN_AREA), "--morph", spec])
                extra[tag] = json.loads((RES / f"{name}_{tag}_summary.json").read_text(encoding="utf-8"))
        runs[name] = {"summary": summ, **extra}
    study["m2_2"] = runs

    md.append("\n## M2.2 — componentes antes/depois (conectividade 8, min-area 20)\n")
    md.append("| Imagem | Contagem manual | Antes: bruto→mantido | 1º plano antes (px) | Depois: bruto→mantido | 1º plano depois (px) |")
    md.append("|---|---:|---|---:|---|---:|")
    for name in (SHAPES, SCENE, BOARD):
        s = runs[name]["summary"]
        a_, b_ = s["initial"], s["final"]
        md.append(f"| {name} | {MANUAL_COUNT[name]} | {a_['selected']['components_raw']}→{a_['selected']['components_kept']} | "
                  f"{a_['foreground_pixels']} | {b_['selected']['components_raw']}→{b_['selected']['components_kept']} | "
                  f"{b_['foreground_pixels']} |")

    md.append("\n## M2.2 — conectividade 4 versus 8 na máscara inicial (sem filtro de área)\n")
    md.append("| Imagem | Componentes (4) | Componentes (8) | Soma das áreas (4) | Soma das áreas (8) | Pixels de 1º plano |")
    md.append("|---|---:|---:|---:|---:|---:|")
    for name in (SHAPES, SCENE, BOARD):
        i = runs[name]["summary"]["initial"]
        md.append(f"| {name} | {i['connectivity_4']['components_raw']} | {i['connectivity_8']['components_raw']} | "
                  f"{i['connectivity_4']['area_raw_sum']} | {i['connectivity_8']['area_raw_sum']} | {i['foreground_pixels']} |")

    md.append("\n## M2.2 — estágios (conectividade 8, min-area 20)\n")
    md.append("| Imagem | Estágio | Operação | Elemento | 1º plano (px) | Brutos | Mantidos |")
    md.append("|---|---:|---|---|---:|---:|---:|")
    for name in (SHAPES, SCENE, BOARD):
        s = runs[name]["summary"]
        md.append(f"| {name} | 0 | máscara inicial | — | {s['initial']['foreground_pixels']} | "
                  f"{s['initial']['selected']['components_raw']} | {s['initial']['selected']['components_kept']} |")
        for st in s["stages"]:
            md.append(f"| {name} | {st['stage']} | {st['op']} | {st['shape']} {st['size']}x{st['size']} x{st['iterations']} | "
                      f"{st['foreground_pixels']} | {st['components_raw']} | {st['components_kept']} |")

    md.append("\n## M2.2 — variações da sequência (ordem inversa e fechamento grande)\n")
    md.append("| Imagem | Sequência | Estágio | Operação | 1º plano (px) | Brutos | Mantidos |")
    md.append("|---|---|---:|---|---:|---:|---:|")
    for name in (SHAPES, SCENE):
        for tag, label in (("ordem_inversa", "close 7 → open 5"), ("fechamento61", "open 5 → close 61")):
            for st in runs[name][tag]["stages"]:
                md.append(f"| {name} | {label} | {st['stage']} | {st['op']} | {st['foreground_pixels']} | "
                          f"{st['components_raw']} | {st['components_kept']} |")

    # Cobertura por elemento na mascara final de SHAPES
    fin = read(RES / f"{SHAPES}_final_mask.png")
    cov_final = level_coverage(fin, read(ROOT / "images/input" / f"{SHAPES}.png"))
    study["m2_2"][SHAPES]["coverage_final"] = cov_final
    md.append("\n## M2.2 — cobertura por elemento em m1_shapes_border_256 após a sequência\n")
    md.append("| " + " | ".join(SHAPE_LEVELS.values()) + " | Fundo marcado (px) |")
    md.append("|" + "---:|" * (len(SHAPE_LEVELS) + 1))
    md.append("| " + " | ".join(f"{100 * cov_final[n]:.0f}%" for n in SHAPE_LEVELS.values())
              + f" | {cov_final['fundo marcado (fp, px)']} |")

    # Figuras M2.2
    for name in (SHAPES, SCENE, BOARD):
        s = runs[name]["summary"]
        a_ = s["initial"]["selected"]
        cv2.imwrite(str(RES / f"fig_m2_2_{name}.png"), panel([
            (read(RES / f"{name}_initial_mask.png"), f"inicial: {a_['components_raw']} brutos"),
            (read(RES / f"{name}_stage1_open.png"), f"1 open e5: {s['stages'][0]['components_raw']} brutos"),
            (read(RES / f"{name}_stage2_close.png"), f"2 close e7: {s['stages'][1]['components_raw']} brutos"),
            (read(RES / f"{name}_labels.png"), f"rotulos (area>={MIN_AREA}): {s['final']['selected']['components_kept']}"),
        ]))
    for name in (SHAPES, SCENE):
        r = runs[name]["ordem_inversa"]
        cv2.imwrite(str(RES / f"fig_m2_2_{name}_ordem_inversa.png"), panel([
            (read(RES / f"{name}_initial_mask.png"), "inicial"),
            (read(RES / f"{name}_ordem_inversa_stage1_close.png"), "1 close e7"),
            (read(RES / f"{name}_ordem_inversa_stage2_open.png"), "2 open e5"),
            (read(RES / f"{name}_ordem_inversa_labels.png"), f"inversa: {r['final']['selected']['components_kept']} mantidos"),
        ]))
    r = runs[SCENE]["fechamento61"]
    cv2.imwrite(str(RES / f"fig_m2_2_{SCENE}_fechamento61.png"), panel([
        (read(RES / f"{SCENE}_initial_mask.png"), "inicial"),
        (read(RES / f"{SCENE}_fechamento61_stage1_open.png"), "1 open e5"),
        (read(RES / f"{SCENE}_fechamento61_stage2_close.png"), "2 close e61"),
        (read(RES / f"{SCENE}_fechamento61_labels.png"), f"rotulos: {r['final']['selected']['components_kept']}"),
    ]))

    (RES / "study_summary.json").write_text(json.dumps(study, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RES / "tabelas.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
