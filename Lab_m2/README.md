# pdi_lab (Python) — Laboratórios M2.1 e M2.2

Projeto único, derivado do `pdi_template` (variante Python, contrato externo versão 2), ampliado com duas operações:

| Operação | Laboratório | O que faz |
|---|---|---|
| `segment` | M2.1 | gera a máscara binária (objeto = 255, fundo = 0) por `fixed`, `otsu`, `adaptive` ou `hsv` |
| `analyze` | M2.2 | rotula componentes conexos, aplica uma sequência morfológica, recontagem, CSV, imagens de estágios e resumo JSON |

As operações da M1 continuam reconhecidas pelo contrato, mas permanecem como *stubs* do template (não fazem parte desta entrega). O OpenCV é usado para limiarização, morfologia e rotulação, como permitem os roteiros.

## 1. Ambiente

Python 3.10+ (testado com 3.13), OpenCV headless 5.0.0.93 e pytest 9.0.2 (`requirements.txt`).

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pytest                     # 71 testes (6 do template + 65 da M2)
python -m pdi_lab --version
```

No Windows use um CPython oficial (não o Python do MSYS2). Detalhes de ambiente: `docs/07-preparacao-do-ambiente-e-erros-comuns.md` do repositório do template.

Os comandos abaixo são executados **a partir da pasta `python/`**. Em vez de `python -m pdi_lab` pode-se usar o executável `pdi_lab` criado por `pip install -e .` caso ele esteja no `PATH`.

## 2. Operação `segment` (M2.1)

```bash
python -m pdi_lab --operation segment \
  --input images/input/m1_gray_scene_256.png \
  --output images/output/m1_gray_scene_256_adaptive_mask.png \
  --method adaptive --block-size 101 --c=-20
```

Regra geral: **o objeto é sempre 255 na saída**. Nas imagens do estudo os objetos são **mais claros** que o entorno, então não se usa `--invert`; para objetos escuros use `--invert true`.

| Parâmetro | Aplica-se a | Valores | Padrão |
|---|---|---|---|
| `--method` | todos | `fixed`, `otsu`, `adaptive`, `hsv` | obrigatório |
| `--threshold` | `fixed` | inteiro 0–255. Sem `--invert`: pixel `> T` vira objeto (pixel `== T` fica no fundo). Com `--invert`: pixel `<= T` vira objeto | obrigatório em `fixed` |
| `--invert` | todos | `true` ou `false` (objeto escuro) | `false` |
| `--blur` | todos | `0` (sem suavização) ou ímpar ≥ 3: tamanho do filtro gaussiano aplicado **antes** do método | `0` |
| `--block-size` | `adaptive` | ímpar ≥ 3 (janela da média gaussiana local) | `31` |
| `--c` | `adaptive` | inteiro; sem `--invert`: pixel `> média − C` (C negativo exige contraste: `--c=-20` marca só o que supera a média local em 20; **valores negativos devem ser escritos com `=`**). Com `--invert`: pixel `<= média − C` | `10` |
| `--hsv-lower`, `--hsv-upper` | `hsv` | `H,S,V` com H 0–179 (escala do OpenCV) e S, V 0–255. Se `H_lower > H_upper` a faixa cruza a descontinuidade do matiz (ex.: vermelho `170,100,100` a `10,255,255`) e é tratada como duas faixas | obrigatórios em `hsv` |

- `otsu` calcula o limiar automaticamente (registrado em `info.otsu_threshold` no JSON).
- `hsv` exige imagem colorida; as imagens de estudo são em tons de cinza, então `hsv` está coberto pelos testes sintéticos (`tests/test_m2_segment.py`).
- A saída deve ser formato sem perdas (`.png`, `.bmp`, `.tif`); JPEG é recusado (código 5).
- Após gravar, o programa **relê o arquivo salvo** e verifica: 1 canal, mesma largura/altura da entrada, `uint8` e somente `{0, 255}`. Falhando, retorna erro e a execução não é considerada bem-sucedida.
- Junto à máscara é criado `<saida>.json` (mesmo nome, extensão `.json`) com método, parâmetros, pixels e proporção de primeiro plano e o resultado dessas verificações. A linha de status também é impressa no terminal.

### As configurações comparadas na M2.1

Sem pré-processamento (as imagens do template são sintéticas e sem ruído). O método e os parâmetros mudam por imagem; o `REPORT.md` justifica cada um.

```bash
# m1_shapes_border_256 (favorável): formas claras sobre fundo escuro
python -m pdi_lab --operation segment --input images/input/m1_shapes_border_256.png \
  --output images/output/m1_shapes_border_256_fixed_mask.png --method fixed --threshold 60
python -m pdi_lab --operation segment --input images/input/m1_shapes_border_256.png \
  --output images/output/m1_shapes_border_256_otsu_mask.png --method otsu
python -m pdi_lab --operation segment --input images/input/m1_shapes_border_256.png \
  --output images/output/m1_shapes_border_256_adaptive_mask.png --method adaptive --block-size 101 --c=-5

# m1_gray_scene_256 (difícil): gradiente de iluminação
python -m pdi_lab --operation segment --input images/input/m1_gray_scene_256.png \
  --output images/output/m1_gray_scene_256_fixed_mask.png --method fixed --threshold 200
python -m pdi_lab --operation segment --input images/input/m1_gray_scene_256.png \
  --output images/output/m1_gray_scene_256_otsu_mask.png --method otsu
python -m pdi_lab --operation segment --input images/input/m1_gray_scene_256.png \
  --output images/output/m1_gray_scene_256_adaptive_mask.png --method adaptive --block-size 101 --c=-20
# tentativa com a polaridade oposta (formas escuras), que documenta a falha
python -m pdi_lab --operation segment --input images/input/m1_gray_scene_256.png \
  --output images/output/m1_gray_scene_256_adaptive_dark_mask.png --method adaptive --block-size 101 --c 3 --invert true
```

Configuração de trabalho levada para a M2.2: `fixed` (T = 60) em `m1_shapes_border_256` e `adaptive` (101, C = −20) em `m1_gray_scene_256`. `tools/run_study.py` executa todos esses comandos (ver seção 5).

## 3. Operação `analyze` (M2.2)

```bash
python -m pdi_lab --operation analyze \
  --input images/output/m1_shapes_border_256_fixed_mask.png \
  --output results/m1_shapes_border_256 \
  --connectivity 8 --min-area 20 \
  --morph open:ellipse:5:1,close:ellipse:7:1
```

`--input` é a máscara binária (aceita só 1 canal, 8 bits, valores `{0, 255}`; outra coisa retorna código 5). `--output` é um **prefixo**.

| Parâmetro | Valores | Padrão |
|---|---|---|
| `--connectivity` | `4` ou `8` (conectividade usada nos CSV e no filtro) | `8` |
| `--min-area` | inteiro ≥ 0. Componente com `area >= min-area` é *mantido* (`kept=true`); `0` não filtra | `0` |
| `--morph` | lista separada por vírgulas de `operação:forma:tamanho:iterações`. Operações: `erode`, `dilate`, `open`, `close`. Formas: `rect`, `ellipse`, `cross`. Tamanho: ímpar ≥ 3. Iterações ≥ 1 | `open:ellipse:3:1,close:ellipse:5:1` |
| `--morph-config` | arquivo JSON equivalente a `--morph` (ver abaixo); não combinar com `--morph` | — |

Regras da sequência (validadas antes de executar): pelo menos **duas** operações, ao menos uma `open` ou `close`, e dois passos consecutivos idênticos são recusados (repetição sem finalidade distinta). O elemento estruturante é sempre quadrado em caixa (`tamanho × tamanho`) com o formato escolhido; a ordem é a da lista.

Arquivo de configuração (`--morph-config sequencia.json`), sem editar código:

```json
{"sequence": [
  {"op": "open",  "shape": "ellipse", "size": 5, "iterations": 1},
  {"op": "close", "shape": "ellipse", "size": 7, "iterations": 1}
]}
```

### Arquivos criados (prefixo `P`, por exemplo `results/m1_shapes_border_256`)

| Arquivo | Conteúdo |
|---|---|
| `P_initial_mask.png` | cópia da máscara de entrada (estágio 0) |
| `P_initial.csv` | componentes da máscara inicial (conectividade escolhida) |
| `P_labels_initial.png` | rótulos coloridos da máscara inicial |
| `P_stage1_<op>.png`, `P_stage2_<op>.png`, … | saída de cada estágio morfológico, na ordem (ex.: `P_stage1_open.png`, `P_stage2_close.png`) |
| `P_final_mask.png` | máscara após o último estágio |
| `P_final.csv` | componentes da máscara final |
| `P_labels.png` | imagem de rótulos da máscara final: componentes mantidos coloridos, com caixa e número; componentes descartados pelo filtro em cinza |
| `P_summary.json` | conectividade, `min_area`, sequência, contagens brutas e filtradas (para conectividade 4 **e** 8), pixels e áreas somadas antes/depois, borda tocada, contagens por estágio |

Formato dos CSV (fundo, rótulo 0, nunca aparece):

```text
label,area,x,y,width,height,cx,cy,kept
```

`x,y,width,height` = caixa delimitadora; `cx,cy` = centroide; `kept` = `true`/`false` conforme `--min-area`. Os rótulos não precisam coincidir entre máscaras. O programa confere que a soma das áreas dos componentes brutos é igual aos pixels de primeiro plano e falha (código 1) se não for.

## 4. Códigos de saída

Os do template: `0` sucesso, `1` erro geral, `2` argumento obrigatório ausente, `3` falha de leitura, `4` falha de escrita, `5` parâmetro inválido, `6` operação desconhecida.

Exemplos da M2: `--method xyz` → 5; `segment` sem `--method` → 2; `--threshold 300` → 5; `--connectivity 3` → 5; `--min-area -1` → 5; entrada inexistente → 3; `--morph-config` inexistente → 3; saída `.jpg` → 5; entrada de `analyze` não binária → 5.

## 5. Reproduzir tudo

```bash
python tools/run_study.py     # executa segment e analyze pela CLI, gera results/ e images/output/
python -m pytest
```

`tools/run_study.py` chama a mesma CLI documentada acima e escreve `results/tabelas.md`, `results/study_summary.json`, `results/m2_1_sensibilidade.csv` e as figuras `results/fig_*.png` usadas no `REPORT.md`.

### Imagens de estudo

Todas são **fornecidas pelo professor** no template (`images/input/m1_*.png`) e não são alteradas por nenhuma operação:

| Imagem | Papel no estudo |
|---|---|
| `m1_shapes_border_256.png` | favorável: 4 formas claras (retângulo, 2 quadrados, círculo) e uma linha diagonal fina, sobre fundo escuro; objetos tocando a borda; a linha liga o círculo a um quadrado (contato) |
| `m1_gray_scene_256.png` | difícil: fundo com gradiente de iluminação e formas de baixo contraste (2 quadrados, 1 faixa, 2 círculos) mais uma linha horizontal fina |
| `m1_checkerboard_256.png` | caso extra, só para comparar conectividade 4 e 8 e o efeito da sequência (quadrados que se tocam só pelos cantos) |

Não há máscara de referência fornecida. Em `m1_shapes_border_256` cada elemento tem um nível de cinza próprio (fundo 30; elementos 85, 130, 170, 210 e 235), o que permite medir a cobertura de cada elemento; nas outras imagens só há proporções, contagens e inspeção visual. As contagens "manuais" citadas no relatório são feitas por inspeção visual.

## 6. Estrutura

```text
src/pdi_lab/
├── __main__.py, cli.py, contract.py, ...   infraestrutura do template (cli/contract estendidos)
├── m2_params.py       parâmetros e validações de segment/analyze
├── segmentation.py    M2.1: métodos, validação e relatório da máscara
├── analysis.py        M2.2: rotulação, morfologia, CSV, rótulos, resumo
└── operations.py      despacho (segment, analyze) + stubs da M1
tests/                 test_cli/test_infrastructure (template), test_m2_segment, test_m2_analyze
tools/                 run_study.py
images/input (imagens do professor), images/output
results/               CSV, JSON, estágios, rótulos e figuras da M2.2
REPORT.md  AI_USAGE.md  lab.json
```

## Critérios da rubrica da M2 e onde estão as evidências

| Critério | M2.1 (`segment`) | M2.2 (`analyze`) |
|---|---|---|
| Execução e reprodução | Seção 2 deste README; `python tools/run_study.py` regenera as máscaras em `images/output/` para as 3 imagens do professor e vários métodos. | Seção 3 deste README; o mesmo script regenera estágios, CSV e resumos em `results/`; `--morph-config` reproduz outro caso sem editar código. |
| Aquisição e requisitos | `REPORT.md`, M2.1 seções 1 a 4: alvo, 3 imagens, limiar fixo contra Otsu, adaptativo e HSV, parâmetros por configuração; `AI_USAGE.md`. | `REPORT.md`, M2.2 seções 1 a 4: máscara da M2.1, conectividade 4 e 8 na mesma máscara, sequência com elemento estruturante, iterações e ordem; CSV, resumo e antes/depois. |
| Corretude | `tests/test_m2_segment.py`: valor do limiar, polaridade, formato 0/255, 1 canal, mesmas dimensões. | `tests/test_m2_analyze.py`: diagonal 4 contra 8, abertura, fechamento, soma das áreas igual aos pixels de primeiro plano, bruto contra filtrado. |
| Guardas | Códigos 2, 3, 4, 5 e 6; JPEG recusado; método desconhecido; parâmetros inválidos. | Máscara inexistente ou não binária, `--connectivity` e `--min-area` inválidos, `--morph` inválido, máscara vazia, objeto na borda. |
| Análise | `REPORT.md`, M2.1 seções 3 a 5: comparação nas mesmas imagens, falsos positivos e negativos, escolha da configuração de trabalho. | `REPORT.md`, M2.2 seções 2 a 7: 4 contra 8, finalidade e ordem de cada operação, benefício e efeito indesejado, contagem contra interpretação humana. |

Declaração de IA: seção 8 do `REPORT.md` e `AI_USAGE.md`.
