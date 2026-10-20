"""Testes da M2.2 — operacao `analyze` (rotulacao, morfologia, CSV, resumo)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from pdi_lab import exit_code
from pdi_lab.__main__ import main
from pdi_lab.analysis import apply_step, label_components
from pdi_lab.m2_params import MorphStep

ROOT = Path(__file__).resolve().parents[1]
SHAPES = "m1_shapes_border_256"   # imagens do template do professor
SCENE = "m1_gray_scene_256"
BOARD = "m1_checkerboard_256"
SEGMENT_ARGS = {
    SHAPES: ["--method", "fixed", "--threshold", "60"],
    SCENE: ["--method", "adaptive", "--block-size", "101", "--c=-20"],
    BOARD: ["--method", "fixed", "--threshold", "128"],
}


def save_mask(path: Path, mask: np.ndarray) -> Path:
    cv2.imwrite(str(path), mask)
    return path


def analyze(tmp_path, mask_path, *extra, prefix="out/r") -> tuple[int, Path]:
    pre = tmp_path / prefix
    code = main(["--operation", "analyze", "--input", str(mask_path), "--output", str(pre), *extra])
    return code, pre


def summary(prefix: Path) -> dict:
    return json.loads(Path(f"{prefix}_summary.json").read_text(encoding="utf-8"))


def read_csv(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------- conectividade 4 versus 8 ----------

def diagonal_mask() -> np.ndarray:
    m = np.zeros((6, 6), np.uint8)
    m[2, 2] = 255
    m[3, 3] = 255   # vizinhos apenas pela diagonal
    return m


def test_diagonal_pixels_connectivity_4_vs_8():
    m = diagonal_mask()
    assert len(label_components(m, 4, 0)[1]) == 2
    assert len(label_components(m, 8, 0)[1]) == 1


def test_diagonal_pixels_through_cli_summary(tmp_path):
    path = save_mask(tmp_path / "diag.png", diagonal_mask())
    # A abertura apaga estes dois pixels; por isso conferimos a contagem da mascara INICIAL.
    code, pre = analyze(tmp_path, path, "--connectivity", "4")
    assert code == 0
    s = summary(pre)
    assert s["initial"]["connectivity_4"]["components_raw"] == 2
    assert s["initial"]["connectivity_8"]["components_raw"] == 1
    assert s["initial"]["selected"]["components_raw"] == 2           # conectividade escolhida = 4
    assert len(read_csv(f"{pre}_initial.csv")) == 2


# ---------- morfologia ----------

def noisy_mask() -> np.ndarray:
    m = np.zeros((40, 40), np.uint8)
    m[10:30, 10:30] = 255      # regiao principal
    m[2, 2] = 255              # ruido isolado
    m[35, 36] = 255
    return m


def test_opening_removes_isolated_noise_and_keeps_main_region():
    m = noisy_mask()
    opened = apply_step(m, MorphStep("open", "rect", 3, 1))
    assert np.count_nonzero(opened[:8, :8]) == 0 and opened[35, 36] == 0
    assert (opened[10:30, 10:30] == 255).all()                      # quadrado 20x20 sobrevive
    assert len(label_components(m, 8, 0)[1]) == 3
    assert len(label_components(opened, 8, 0)[1]) == 1


def test_closing_fills_small_hole():
    m = np.zeros((30, 30), np.uint8)
    m[5:25, 5:25] = 255
    m[14, 14] = 0                                                   # furo de 1 pixel
    closed = apply_step(m, MorphStep("close", "rect", 3, 1))
    assert closed[14, 14] == 255
    assert np.count_nonzero(closed) == 20 * 20


def test_cli_sequence_stages_and_summary(tmp_path):
    path = save_mask(tmp_path / "noisy.png", noisy_mask())
    code, pre = analyze(tmp_path, path, "--connectivity", "8", "--min-area", "10",
                        "--morph", "open:rect:3:1,close:rect:3:1")
    assert code == exit_code.SUCCESS
    s = summary(pre)
    assert [st["op"] for st in s["stages"]] == ["open", "close"]
    assert s["initial"]["selected"]["components_raw"] == 3
    assert s["initial"]["selected"]["components_kept"] == 1         # filtro de area
    assert s["final"]["selected"]["components_raw"] == 1
    for st in s["stages"]:                                          # cada estagio salvo em PNG
        assert Path(st["file"]).is_file()
    assert Path(f"{pre}_initial_mask.png").is_file() and Path(f"{pre}_labels.png").is_file()
    # a mascara inicial preservada e identica a de entrada
    assert np.array_equal(cv2.imread(f"{pre}_initial_mask.png", -1), noisy_mask())


# ---------- CSV ----------

def test_csv_columns_and_values(tmp_path):
    m = np.zeros((20, 20), np.uint8)
    m[5:9, 6:12] = 255                                              # 4 linhas x 6 colunas, area 24
    m[15, 15] = 255                                                 # componente de 1 pixel
    path = save_mask(tmp_path / "m.png", m)
    code, pre = analyze(tmp_path, path, "--min-area", "5", "--morph", "close:rect:3:1,open:rect:3:1")
    assert code == 0
    with open(f"{pre}_initial.csv", encoding="utf-8") as f:
        assert f.readline().strip() == "label,area,x,y,width,height,cx,cy,kept"
    rows = read_csv(f"{pre}_initial.csv")
    big = next(r for r in rows if r["area"] == "24")
    assert (big["x"], big["y"], big["width"], big["height"]) == ("6", "5", "6", "4")
    assert (float(big["cx"]), float(big["cy"])) == (8.5, 6.5)
    assert big["kept"] == "true"
    small = next(r for r in rows if r["area"] == "1")
    assert small["kept"] == "false"                                  # filtrado por --min-area 5
    assert "0" not in {r["label"] for r in rows}                     # fundo fora do CSV


# ---------- casos de borda ----------

def test_empty_mask_has_zero_components(tmp_path):
    path = save_mask(tmp_path / "empty.png", np.zeros((16, 16), np.uint8))
    code, pre = analyze(tmp_path, path)
    assert code == 0
    s = summary(pre)
    assert s["initial"]["selected"]["components_raw"] == 0
    assert s["final"]["selected"]["components_raw"] == 0
    assert s["initial"]["foreground_pixels"] == 0
    assert read_csv(f"{pre}_final.csv") == []                        # so o cabecalho


def test_object_touching_border_is_counted_and_flagged(tmp_path):
    m = np.zeros((20, 20), np.uint8)
    m[0:6, 0:6] = 255                                                # encosta no canto
    m[10:16, 10:16] = 255
    path = save_mask(tmp_path / "b.png", m)
    code, pre = analyze(tmp_path, path)
    assert code == 0
    s = summary(pre)
    assert s["initial"]["selected"]["components_raw"] == 2
    assert s["initial"]["selected"]["touching_border"] == 1
    assert s["final"]["selected"]["components_raw"] == 2             # abertura/fechamento mantem o objeto da borda


def test_full_foreground_mask_is_one_component(tmp_path):
    path = save_mask(tmp_path / "full.png", np.full((12, 12), 255, np.uint8))
    code, pre = analyze(tmp_path, path)
    assert code == 0 and summary(pre)["initial"]["selected"]["components_raw"] == 1


# ---------- parametros e codigos de saida ----------

@pytest.mark.parametrize(
    "args, expected",
    [
        (["--connectivity", "3"], exit_code.INVALID_PARAMETER),
        (["--connectivity", "abc"], exit_code.INVALID_PARAMETER),
        (["--connectivity", "6"], exit_code.INVALID_PARAMETER),
        (["--min-area", "-1"], exit_code.INVALID_PARAMETER),
        (["--min-area", "dez"], exit_code.INVALID_PARAMETER),
        (["--morph", "open:rect:3:1"], exit_code.INVALID_PARAMETER),                  # so uma operacao
        (["--morph", "erode:rect:3:1,dilate:rect:3:1"], exit_code.INVALID_PARAMETER), # sem open/close
        (["--morph", "open:rect:3:1,open:rect:3:1"], exit_code.INVALID_PARAMETER),   # repeticao identica
        (["--morph", "open:rect:4:1,close:rect:3:1"], exit_code.INVALID_PARAMETER),   # tamanho par
        (["--morph", "open:rect:3:0,close:rect:3:1"], exit_code.INVALID_PARAMETER),   # 0 iteracoes
        (["--morph", "abrir:rect:3:1,close:rect:3:1"], exit_code.INVALID_PARAMETER),
        (["--morph", "open:rect:3,close:rect:3:1"], exit_code.INVALID_PARAMETER),
        (["--morph", "open:rect:3:1,close:rect:3:1", "--morph-config", "x.json"], exit_code.INVALID_PARAMETER),
        (["--morph-config", "nao_existe.json"], exit_code.READ_ERROR),
    ],
)
def test_invalid_analyze_parameters(tmp_path, args, expected):
    path = save_mask(tmp_path / "m.png", noisy_mask())
    code, pre = analyze(tmp_path, path, *args)
    assert code == expected and code != 0
    assert not Path(f"{pre}_summary.json").exists()


def test_non_binary_input_is_rejected(tmp_path):
    gray = np.full((8, 8), 128, np.uint8)
    code, _ = analyze(tmp_path, save_mask(tmp_path / "g.png", gray))
    assert code == exit_code.INVALID_PARAMETER


def test_color_input_is_rejected(tmp_path):
    code, _ = analyze(tmp_path, save_mask(tmp_path / "c.png", np.zeros((8, 8, 3), np.uint8)))
    assert code == exit_code.INVALID_PARAMETER


def test_missing_input_is_read_error(tmp_path):
    code, _ = analyze(tmp_path, tmp_path / "nao_existe.png")
    assert code == exit_code.READ_ERROR


def test_morph_config_file_reproduces_other_case(tmp_path):
    cfg = tmp_path / "morph.json"
    cfg.write_text(json.dumps({"sequence": [
        {"op": "open", "shape": "rect", "size": 3, "iterations": 1},
        {"op": "close", "shape": "ellipse", "size": 3, "iterations": 1}]}), encoding="utf-8")
    path = save_mask(tmp_path / "noisy.png", noisy_mask())
    code, pre = analyze(tmp_path, path, "--morph-config", str(cfg))
    assert code == 0
    s = summary(pre)
    assert s["sequence_source"] == "arquivo:morph.json"
    assert s["sequence"][1]["shape"] == "ellipse"


def test_default_connectivity_and_sequence_are_documented_values(tmp_path):
    path = save_mask(tmp_path / "noisy.png", noisy_mask())
    code, pre = analyze(tmp_path, path)
    s = summary(pre)
    assert code == 0 and s["connectivity"] == 8 and s["min_area"] == 0
    assert s["sequence_source"] == "padrao" and len(s["sequence"]) == 2


# ---------- reexecucao das imagens do estudo ----------

def segment_study_image(tmp_path, name) -> Path:
    mask = tmp_path / f"{name}_mask.png"
    code = main(["--operation", "segment", "--input", str(ROOT / "images/input" / f"{name}.png"),
                 "--output", str(mask), *SEGMENT_ARGS[name]])
    assert code == 0
    return mask


@pytest.mark.parametrize("name", [SHAPES, SCENE, BOARD])
def test_study_images_end_to_end_and_area_sum(tmp_path, name):
    """segment (M2.1) continua funcionando e analyze confere soma das areas (M2.2)."""
    mask = segment_study_image(tmp_path, name)
    foreground = int(np.count_nonzero(cv2.imread(str(mask), -1)))

    code, pre = analyze(tmp_path, mask, "--connectivity", "8", "--min-area", "20",
                        "--morph", "open:ellipse:5:1,close:ellipse:7:1", prefix=f"res/{name}")
    assert code == 0
    s = summary(pre)

    # soma das areas BRUTAS (antes de qualquer filtro) == pixels de primeiro plano
    initial_rows = read_csv(f"{pre}_initial.csv")
    assert sum(int(r["area"]) for r in initial_rows) == foreground == s["initial"]["foreground_pixels"]
    final_mask = cv2.imread(f"{pre}_final_mask.png", -1)
    final_rows = read_csv(f"{pre}_final.csv")
    assert sum(int(r["area"]) for r in final_rows) == int(np.count_nonzero(final_mask))

    for conn in ("connectivity_4", "connectivity_8"):                # as duas conectividades batem
        assert s["initial"][conn]["area_raw_sum"] == foreground
    assert sum(r["kept"] == "true" for r in initial_rows) == s["initial"]["selected"]["components_kept"]
    assert all(int(r["area"]) >= 20 for r in initial_rows if r["kept"] == "true")
    assert all(int(r["area"]) < 20 for r in initial_rows if r["kept"] == "false")
    for key in ("labels", "labels_initial", "final_mask", "initial_mask", "final_csv", "initial_csv"):
        assert Path(s["files"][key]).is_file()


def test_shapes_image_contact_border_and_sequence(tmp_path):
    """m1_shapes_border_256: a linha fina liga circulo e quadrado; a abertura corta a ligacao."""
    mask = segment_study_image(tmp_path, SHAPES)
    code, pre = analyze(tmp_path, mask, "--connectivity", "8", "--min-area", "20",
                        "--morph", "open:ellipse:5:1,close:ellipse:7:1")
    assert code == 0
    s = summary(pre)
    # inicial: 3 componentes; circulo + linha + quadrado superior direito formam UM so (contato)
    assert s["initial"]["selected"]["components_raw"] == 3
    initial = read_csv(f"{pre}_initial.csv")
    assert max(int(r["area"]) for r in initial) == 14573
    assert s["initial"]["selected"]["touching_border"] == 3         # os tres tocam a borda
    # final: a linha some e as formas se separam; sobra 1 fragmento de 7 px no canto, descartado
    assert s["final"]["selected"]["components_raw"] == 5
    assert s["final"]["selected"]["components_kept"] == 4
    final = read_csv(f"{pre}_final.csv")
    small = [r for r in final if r["kept"] == "false"]
    assert [int(r["area"]) for r in small] == [7] and (small[0]["x"], small[0]["y"]) == ("0", "253")
    assert 9667 in {int(r["area"]) for r in final}                    # circulo isolado
    # objeto que toca a borda continua sendo contado (retangulo em x = 0)
    assert any(r["x"] == "0" and r["y"] == "20" and r["kept"] == "true" for r in final)


def test_checkerboard_connectivity_and_opening_vs_closing(tmp_path):
    """Tabuleiro: quadrados so se tocam pelos cantos. 4 -> 128 componentes; 8 -> 1."""
    mask = segment_study_image(tmp_path, BOARD)
    code, pre = analyze(tmp_path, mask, "--connectivity", "8", "--morph", "open:ellipse:5:1,close:ellipse:7:1")
    assert code == 0
    s = summary(pre)
    assert s["initial"]["connectivity_4"]["components_raw"] == 128
    assert s["initial"]["connectivity_8"]["components_raw"] == 1
    # a abertura separa os 128 quadrados (rompe os contatos de canto)...
    assert s["stages"][0]["op"] == "open" and s["stages"][0]["components_raw"] == 128
    # ...e o fechamento seguinte os funde de novo: a sequencia desfaz a propria separacao
    assert s["stages"][1]["op"] == "close" and s["stages"][1]["components_raw"] == 1


def test_scene_adaptive_mask_sequence_removes_line_only(tmp_path):
    """m1_gray_scene_256: a abertura apaga a linha horizontal fina; o fechamento 7x7 nao corrige o 'C'."""
    mask = segment_study_image(tmp_path, SCENE)
    code, pre = analyze(tmp_path, mask, "--min-area", "20", "--morph", "open:ellipse:5:1,close:ellipse:7:1")
    assert code == 0
    initial = read_csv(f"{pre}_initial.csv")
    assert sorted(int(r["area"]) for r in initial) == [512, 2245]    # linha (256x2) e quadrado claro vazado
    final = read_csv(f"{pre}_final.csv")
    assert 512 not in {int(r["area"]) for r in final}                 # linha removida
    assert sum(int(r["area"]) for r in final) < sum(int(r["area"]) for r in initial)
