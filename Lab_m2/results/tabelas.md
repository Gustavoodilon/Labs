## M2.1 — proporção de primeiro plano e componentes (conectividade 8, sem filtro)

| Imagem | Configuração | Parâmetros | 1º plano (px) | Proporção | Componentes | Maior componente (px) |
|---|---|---|---:|---:|---:|---:|
| m1_shapes_border_256 | fixed | fixed: invert=False, blur=0, threshold=60 | 21835 | 33.32% | 3 | 14573 |
| m1_shapes_border_256 | otsu | otsu: invert=False, blur=0, limiar calculado=85 | 19259 | 29.39% | 2 | 14573 |
| m1_shapes_border_256 | adaptive | adaptive: invert=False, blur=0, block_size=101, c=-5 | 19092 | 29.13% | 3 | 12148 |
| m1_gray_scene_256 | fixed | fixed: invert=False, blur=0, threshold=200 | 9353 | 14.27% | 2 | 5041 |
| m1_gray_scene_256 | otsu | otsu: invert=False, blur=0, limiar calculado=133 | 30606 | 46.70% | 1 | 30606 |
| m1_gray_scene_256 | adaptive | adaptive: invert=False, blur=0, block_size=101, c=-20 | 2757 | 4.21% | 2 | 2245 |
| m1_gray_scene_256 | adaptive_dark | adaptive: invert=True, blur=0, block_size=101, c=3 | 25249 | 38.53% | 17 | 8920 |
| m1_checkerboard_256 | fixed | fixed: invert=False, blur=0, threshold=128 | 32768 | 50.00% | 1 | 32768 |

## M2.1 — cobertura por elemento em m1_shapes_border_256 (fração dos pixels de cada elemento marcada)

| Configuração | quadrado inferior | quadrado superior direito | linha diagonal | retangulo superior esquerdo | circulo | Fundo marcado (px) |
|---|---:|---:|---:|---:|---:|---:|
| fixed | 100% | 100% | 100% | 100% | 100% | 0 |
| otsu | 0% | 100% | 100% | 100% | 100% | 0 |
| adaptive | 88% | 59% | 74% | 100% | 95% | 0 |

## M2.2 — componentes antes/depois (conectividade 8, min-area 20)

| Imagem | Contagem manual | Antes: bruto→mantido | 1º plano antes (px) | Depois: bruto→mantido | 1º plano depois (px) |
|---|---:|---|---:|---|---:|
| m1_shapes_border_256 | 5 | 3→3 | 21835 | 5→4 | 21263 |
| m1_gray_scene_256 | 5 | 2→2 | 2757 | 2→2 | 2131 |
| m1_checkerboard_256 | 128 | 1→1 | 32768 | 1→1 | 34568 |

## M2.2 — conectividade 4 versus 8 na máscara inicial (sem filtro de área)

| Imagem | Componentes (4) | Componentes (8) | Soma das áreas (4) | Soma das áreas (8) | Pixels de 1º plano |
|---|---:|---:|---:|---:|---:|
| m1_shapes_border_256 | 3 | 3 | 21835 | 21835 | 21835 |
| m1_gray_scene_256 | 2 | 2 | 2757 | 2757 | 2757 |
| m1_checkerboard_256 | 128 | 1 | 32768 | 32768 | 32768 |

## M2.2 — estágios (conectividade 8, min-area 20)

| Imagem | Estágio | Operação | Elemento | 1º plano (px) | Brutos | Mantidos |
|---|---:|---|---|---:|---:|---:|
| m1_shapes_border_256 | 0 | máscara inicial | — | 21835 | 3 | 3 |
| m1_shapes_border_256 | 1 | open | ellipse 5x5 x1 | 21262 | 5 | 4 |
| m1_shapes_border_256 | 2 | close | ellipse 7x7 x1 | 21263 | 5 | 4 |
| m1_gray_scene_256 | 0 | máscara inicial | — | 2757 | 2 | 2 |
| m1_gray_scene_256 | 1 | open | ellipse 5x5 x1 | 2130 | 2 | 2 |
| m1_gray_scene_256 | 2 | close | ellipse 7x7 x1 | 2131 | 2 | 2 |
| m1_checkerboard_256 | 0 | máscara inicial | — | 32768 | 1 | 1 |
| m1_checkerboard_256 | 1 | open | ellipse 5x5 x1 | 31868 | 128 | 128 |
| m1_checkerboard_256 | 2 | close | ellipse 7x7 x1 | 34568 | 1 | 1 |

## M2.2 — variações da sequência (ordem inversa e fechamento grande)

| Imagem | Sequência | Estágio | Operação | 1º plano (px) | Brutos | Mantidos |
|---|---|---:|---|---:|---:|---:|
| m1_shapes_border_256 | close 7 → open 5 | 1 | close | 21856 | 3 | 3 |
| m1_shapes_border_256 | close 7 → open 5 | 2 | open | 21323 | 5 | 4 |
| m1_shapes_border_256 | open 5 → close 61 | 1 | open | 21262 | 5 | 4 |
| m1_shapes_border_256 | open 5 → close 61 | 2 | close | 24501 | 3 | 2 |
| m1_gray_scene_256 | close 7 → open 5 | 1 | close | 2759 | 2 | 2 |
| m1_gray_scene_256 | close 7 → open 5 | 2 | open | 2136 | 2 | 2 |
| m1_gray_scene_256 | open 5 → close 61 | 1 | open | 2130 | 2 | 2 |
| m1_gray_scene_256 | open 5 → close 61 | 2 | close | 7228 | 1 | 1 |

## M2.2 — cobertura por elemento em m1_shapes_border_256 após a sequência

| quadrado inferior | quadrado superior direito | linha diagonal | retangulo superior esquerdo | circulo | Fundo marcado (px) |
|---:|---:|---:|---:|---:|---:|
| 100% | 100% | 56% | 100% | 100% | 1 |
