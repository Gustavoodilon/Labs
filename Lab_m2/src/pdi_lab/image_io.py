from __future__ import annotations

import cv2
import numpy as np

from . import exit_code
from .errors import PdiError
from .result_io import ensure_parent_directory


def read_image(path: str) -> np.ndarray:
    """Lê a imagem preservando canais e profundidade do arquivo."""

    image = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise PdiError(exit_code.READ_ERROR, f"Nao foi possivel abrir a imagem: {path}")
    return image


def write_image(path: str, image: np.ndarray) -> None:
    """Salva a imagem e cria automaticamente os diretórios-pai."""

    if image is None or image.size == 0:
        raise PdiError(exit_code.WRITE_ERROR, "A imagem de saida esta vazia.")

    try:
        output = ensure_parent_directory(path)
    except OSError as error:
        raise PdiError(
            exit_code.WRITE_ERROR,
            f"Nao foi possivel preparar o caminho de saida: {error}",
        ) from error

    if not cv2.imwrite(str(output), image):
        raise PdiError(exit_code.WRITE_ERROR, f"Nao foi possivel salvar a imagem: {path}")
