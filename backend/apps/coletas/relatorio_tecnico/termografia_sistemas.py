"""Módulos de relatório da termografia de sistemas mecânicos e de processos (Anexo I 2.3.2.2.2–4).

Mesma família da termografia elétrica (medições térmicas, ΔT, imagem térmica), com glossário e
considerações do relatório de referência. Sem o bloco de correntes e de carga elétrica: o
`docs/12` registra que a carga elétrica não se aplica a sistemas mecânicos nem a processos.

- `TERMOGRAFIA_MECANICA`: sistemas mecânicos dinâmicos e estáticos (`sistema` MEC_DINAMICO ou MEC_ESTATICO);
- `TERMO_PROCESSOS`: processos industriais (`sistema` PROCESSO).

A ΔT é aritmética. A condição não é classificada por um limite genérico: depende de critério da
aplicação, cadastrado e validado (ver `docs/12`).
"""
from apps.coletas.relatorio_tecnico.inspecao import ModuloInspecaoRota, MEDIA_TEMPERATURA
from apps.coletas.relatorio_tecnico.termografia import CONSIDERACOES_TERMOGRAFIA, GLOSSARIO_TERMOGRAFIA

MODULO_TERMOGRAFIA_MECANICA = ModuloInspecaoRota(
    chave="TERMOGRAFIA_MECANICA",
    medias=(MEDIA_TEMPERATURA,),
    carta_glossario=GLOSSARIO_TERMOGRAFIA,
    carta_consideracoes=CONSIDERACOES_TERMOGRAFIA,
    carta_quebras_glossario=("6.3",),
)

MODULO_TERMO_PROCESSOS = ModuloInspecaoRota(
    chave="TERMO_PROCESSOS",
    medias=(MEDIA_TEMPERATURA,),
    carta_glossario=GLOSSARIO_TERMOGRAFIA,
    carta_consideracoes=CONSIDERACOES_TERMOGRAFIA,
    carta_quebras_glossario=("6.3",),
)
