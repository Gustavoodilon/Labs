# Imagens-base da M1

Este diretório contém imagens sintéticas e determinísticas fornecidas para os Laboratórios M1.1, M1.2 e M1.3.

Elas têm dois papéis complementares:

- **experimento visual:** imagens maiores permitem observar os efeitos das operações;
- **validação previsível:** imagens pequenas permitem calcular ou conferir resultados manualmente.

| Arquivo | Uso sugerido |
|---|---|
| `m1_color_2x2.png` | canais BGR e conversões para cinza |
| `m1_color_scene_256.png` | canais e níveis de cinza em cena colorida |
| `m1_gray_ramp_256.png` | brilho, contraste, negativo, limiar e quantização |
| `m1_gray_steps_16levels.png` | quantização e histogramas |
| `m1_gray_scene_256.png` | transformações e filtros em imagem variada |
| `m1_constant_128_64.png` | guardas, histograma e resposta de filtros |
| `m1_impulse_33.png` | resposta de kernels e convolução |
| `m1_step_vertical_128.png` | resposta de gradiente a transição vertical |
| `m1_step_horizontal_128.png` | resposta de gradiente a transição horizontal |
| `m1_shapes_border_256.png` | comparação de estratégias de borda |
| `m1_checkerboard_256.png` | suavização e perda de detalhes |
| `m1_gray_5x5.png` | conferência manual de convolução |

A pasta `reference/` registra os valores exatos dos casos pequenos. Esses arquivos são dados de apoio; não contêm a implementação dos algoritmos.

Não altere as imagens-base antes de processá-las. Imagens adicionais podem ser criadas com nomes diferentes.
