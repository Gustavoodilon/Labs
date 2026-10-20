"""Testes da M2.1 — operacao `segment` e validacao da mascara binaria."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from pdi_lab import exit_code
from pdi_lab.__main__ import main
from pdi_lab.m2_params import SegmentParams
from pdi_lab.segmentation import check_binary_mask, segment_mask

ROOT = Path(__file__).resolve().parents[1]
SHAPES = "m1_shapes_border_256"   # imagens do template do professor
SCENE = "m1_gray_scene_256"
STUDY_CASES = [
    (SHAPES, ["--method", "fixed", "--threshold", "60"]),
    (SHAPES, ["--method", "otsu"]),
    (SCENE, ["--method", "fixed", "--threshold", "200"]),
    (SCENE, ["--method", "adaptive", "--block-size", "101", "--c=-20"]),
]


def write_gray(path: Path, rows) -> Path:
    cv2.imwrite(str(path), np.array(rows, dtype=np.uint8))
    return path


def run_segment(tmp_path, image, *extra, out="mask.png") -> tuple[int, Path]:
    output = tmp_path / out
    code = main(["--operation", "segment", "--input", str(image), "--output", str(output), *extra])
    return code, output


# ---------- limiar fixo previsivel (pixels antes, no e depois do limiar) ----------

def test_fixed_threshold_both_sides_of_the_limit(tmp_path):
    image = write_gray(tmp_path / "t.png", [[0, 99, 100, 101, 255]])
    code, out = run_segment(tmp_path, image, "--method", "fixed", "--threshold", "100")
    assert code == exit_code.SUCCESS
    # regra documentada: pixel > T vira objeto (255); pixel == T fica no fundo.
    assert cv2.imread(str(out), cv2.IMREAD_UNCHANGED).tolist() == [[0, 0, 0, 255, 255]]


def test_fixed_threshold_inverted_for_dark_objects(tmp_path):
    image = write_gray(tmp_path / "t.png", [[0, 99, 100, 101, 255]])
    code, out = run_segment(tmp_path, image, "--method", "fixed", "--threshold", "100", "--invert", "true")
    assert code == exit_code.SUCCESS
    assert cv2.imread(str(out), cv2.IMREAD_UNCHANGED).tolist() == [[255, 255, 255, 0, 0]]


def test_threshold_extremes(tmp_path):
    image = write_gray(tmp_path / "t.png", [[0, 1, 254, 255]])
    _, out0 = run_segment(tmp_path, image, "--method", "fixed", "--threshold", "0", out="a.png")
    _, out255 = run_segment(tmp_path, image, "--method", "fixed", "--threshold", "255", out="b.png")
    assert cv2.imread(str(out0), -1).tolist() == [[0, 255, 255, 255]]
    assert cv2.imread(str(out255), -1).tolist() == [[0, 0, 0, 0]]


# ---------- outros metodos ----------

def test_otsu_separates_two_levels(tmp_path):
    rows = np.full((20, 20), 40, np.uint8)
    rows[:, 10:] = 200
    image = tmp_path / "bi.png"
    cv2.imwrite(str(image), rows)
    code, out = run_segment(tmp_path, image, "--method", "otsu")
    mask = cv2.imread(str(out), -1)
    assert code == 0
    assert (mask[:, 10:] == 255).all() and (mask[:, :10] == 0).all()
    info = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))["info"]
    assert 40 <= info["otsu_threshold"] < 200


def _gradient_with_dark_block(tmp_path) -> Path:
    gradient = np.tile(np.linspace(80, 230, 120, dtype=np.float32), (120, 1))
    gradient[50:70, 50:70] -= 60                                    # objeto escuro 20x20
    image = tmp_path / "g.png"
    cv2.imwrite(str(image), gradient.astype(np.uint8))
    return image


def test_adaptive_detects_dark_blob_on_gradient(tmp_path):
    image = _gradient_with_dark_block(tmp_path)
    code, out = run_segment(tmp_path, image, "--method", "adaptive", "--block-size", "61",
                            "--c", "10", "--invert", "true")
    mask = cv2.imread(str(out), -1)
    assert code == 0
    assert (mask[50:70, 50:70] == 255).all()                        # objeto inteiro
    assert np.count_nonzero(mask) == 400                            # e nada alem dele
    # um limiar global nao serve: o fundo claro e o objeto compartilham niveis de cinza
    _, fixed = run_segment(tmp_path, image, "--method", "fixed", "--threshold", "120",
                           "--invert", "true", out="fixed.png")
    assert np.count_nonzero(cv2.imread(str(fixed), -1)) > 1000


def test_adaptive_block_smaller_than_object_leaves_hollow_core(tmp_path):
    """Limitacao documentada: com bloco (31) pouco maior que o objeto (20), so a borda e marcada."""
    image = _gradient_with_dark_block(tmp_path)
    code, out = run_segment(tmp_path, image, "--method", "adaptive", "--block-size", "31",
                            "--c", "10", "--invert", "true")
    mask = cv2.imread(str(out), -1)
    assert code == 0
    assert mask[58:62, 58:62].max() == 0                            # miolo vazio
    assert mask[50:70, 50:70].mean() > 150                          # mas a borda foi detectada


def _color_image() -> np.ndarray:
    img = np.zeros((10, 30, 3), np.uint8)
    img[:, :10] = (0, 0, 255)      # vermelho puro: H = 0
    img[:, 10:20] = (0, 255, 0)    # verde: H = 60
    img[:, 20:] = (30, 0, 255)     # vermelho-arroxeado: H ~ 176 (do outro lado do matiz)
    return img


def test_hsv_with_hue_wraparound(tmp_path):
    image = tmp_path / "c.png"
    cv2.imwrite(str(image), _color_image())
    # faixa 170..10 cruza a descontinuidade do matiz: pega H=0 e H~176, nao o verde.
    code, out = run_segment(tmp_path, image, "--method", "hsv",
                            "--hsv-lower", "170,100,100", "--hsv-upper", "10,255,255")
    mask = cv2.imread(str(out), -1)
    assert code == 0
    assert (mask[:, :10] == 255).all() and (mask[:, 20:] == 255).all()
    assert (mask[:, 10:20] == 0).all()
    assert json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))["info"]["hue_wraparound"]


def test_hsv_requires_color_image(tmp_path):
    image = write_gray(tmp_path / "g.png", [[10, 20], [30, 40]])
    code, _ = run_segment(tmp_path, image, "--method", "hsv",
                          "--hsv-lower", "0,0,0", "--hsv-upper", "10,255,255")
    assert code == exit_code.INVALID_PARAMETER


# ---------- falhas e codigos de saida ----------

@pytest.mark.parametrize(
    "args, expected",
    [
        (["--method", "xyz"], exit_code.INVALID_PARAMETER),                     # metodo desconhecido
        ([], exit_code.INVALID_ARGUMENTS),                                       # sem --method
        (["--method", "fixed"], exit_code.INVALID_ARGUMENTS),                    # sem --threshold
        (["--method", "fixed", "--threshold", "300"], exit_code.INVALID_PARAMETER),
        (["--method", "fixed", "--threshold", "-1"], exit_code.INVALID_PARAMETER),
        (["--method", "fixed", "--threshold", "abc"], exit_code.INVALID_PARAMETER),
        (["--method", "fixed", "--threshold", "5", "--blur", "4"], exit_code.INVALID_PARAMETER),
        (["--method", "fixed", "--threshold", "5", "--invert", "talvez"], exit_code.INVALID_PARAMETER),
        (["--method", "adaptive", "--block-size", "10"], exit_code.INVALID_PARAMETER),
        (["--method", "hsv"], exit_code.INVALID_ARGUMENTS),
        (["--method", "hsv", "--hsv-lower", "0,0", "--hsv-upper", "1,1,1"], exit_code.INVALID_PARAMETER),
        (["--method", "hsv", "--hsv-lower", "200,0,0", "--hsv-upper", "1,1,1"], exit_code.INVALID_PARAMETER),
    ],
)
def test_invalid_segment_parameters(tmp_path, args, expected):
    image = write_gray(tmp_path / "t.png", [[1, 2], [3, 4]])
    code, out = run_segment(tmp_path, image, *args)
    assert code == expected
    assert code != 0
    assert not out.exists()


def test_missing_input_is_read_error(tmp_path):
    code, _ = run_segment(tmp_path, tmp_path / "nao_existe.png", "--method", "fixed", "--threshold", "10")
    assert code == exit_code.READ_ERROR


def test_corrupt_input_is_read_error(tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"isto nao e um png")
    code, _ = run_segment(tmp_path, bad, "--method", "fixed", "--threshold", "10")
    assert code == exit_code.READ_ERROR


def test_lossy_output_is_rejected(tmp_path):
    image = write_gray(tmp_path / "t.png", [[1, 2], [3, 4]])
    code, out = run_segment(tmp_path, image, "--method", "fixed", "--threshold", "2", out="mask.jpg")
    assert code == exit_code.INVALID_PARAMETER
    assert not out.exists()


# ---------- verificacao automatica da mascara de saida ----------

def test_check_binary_mask_detects_problems():
    good = np.array([[0, 255], [255, 0]], np.uint8)
    assert check_binary_mask(good, (2, 2))["ok"]
    assert not check_binary_mask(np.array([[0, 128]], np.uint8), (1, 2))["ok"]      # valor 128
    assert not check_binary_mask(good, (3, 3))["ok"]                                  # dimensoes
    assert not check_binary_mask(np.zeros((2, 2, 3), np.uint8), (2, 2))["ok"]        # 3 canais


@pytest.mark.parametrize("name, extra", STUDY_CASES, ids=["shapes-fixed", "shapes-otsu", "scene-fixed", "scene-adaptive"])
def test_study_images_with_two_configurations(tmp_path, name, extra):
    source = ROOT / "images" / "input" / f"{name}.png"
    original = cv2.imread(str(source), cv2.IMREAD_UNCHANGED)
    code, out = run_segment(tmp_path, source, *extra)
    assert code == exit_code.SUCCESS

    mask = cv2.imread(str(out), cv2.IMREAD_UNCHANGED)
    assert mask.ndim == 2 and mask.dtype == np.uint8
    assert mask.shape == original.shape[:2]
    assert {int(v) for v in np.unique(mask)} <= {0, 255}

    report = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert report["foreground_pixels"] == int(np.count_nonzero(mask))
    assert report["checks"]["ok"] is True
    assert 0.0 < report["foreground_ratio"] < 1.0
    # a imagem original nao pode ser alterada pelo processamento
    assert np.array_equal(cv2.imread(str(source), cv2.IMREAD_UNCHANGED), original)


# Elementos de m1_shapes_border_256: cada um tem um nivel de cinza proprio (fundo = 30).
SHAPE_LEVELS = (85, 130, 170, 210, 235)


def _shapes():
    return cv2.imread(str(ROOT / "images" / "input" / f"{SHAPES}.png"), cv2.IMREAD_UNCHANGED)


def _covered(mask, image):
    return [bool((mask[image == lv] > 0).mean() >= 0.5) for lv in SHAPE_LEVELS]


def test_fixed_threshold_is_sensitive_on_shapes_image():
    """Limiar entre o fundo (30) e o elemento mais escuro (85) pega tudo; T=100 perde o elemento 85."""
    image = _shapes()
    ok, _ = segment_mask(image, SegmentParams("fixed", threshold=60))
    assert all(_covered(ok, image)) and (ok[image == 30] == 0).all()
    low, _ = segment_mask(image, SegmentParams("fixed", threshold=100))
    assert _covered(low, image) == [False, True, True, True, True]
    # limite exato: pixel == T fica no fundo, entao T=85 ja perde o elemento de nivel 85
    edge, _ = segment_mask(image, SegmentParams("fixed", threshold=85))
    assert _covered(edge, image)[0] is False


def test_otsu_misses_darkest_element_on_shapes_image():
    image = _shapes()
    mask, info = segment_mask(image, SegmentParams("otsu"))
    assert info["otsu_threshold"] == 85.0
    assert _covered(mask, image) == [False, True, True, True, True]


def test_fixed_threshold_fails_on_uneven_illumination():
    """Limitacao observavel: na cena com gradiente nenhum limiar global isola as formas claras."""
    scene = cv2.imread(str(ROOT / "images" / "input" / f"{SCENE}.png"), cv2.IMREAD_UNCHANGED)
    from pdi_lab.analysis import label_components

    def components(t):
        mask, _ = segment_mask(scene, SegmentParams("fixed", threshold=t))
        return label_components(mask, 8, 0)[1]

    low = components(150)
    assert len(low) == 1 and low[0].area > 20000                    # fundo claro inteiro invade a mascara
    best = components(200)
    assert len(best) == 2
    square = [c for c in best if c.area == 71 * 71]
    other = [c for c in best if c.area != 71 * 71]
    assert len(square) == 1                                          # o quadrado claro sai exato...
    assert other[0].area > 4000 and other[0].width == 256            # ...junto de fundo claro + linha que atravessam a imagem
