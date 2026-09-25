"""
Registro dos módulos técnicos do relatório.

Cada tecnologia aponta para um módulo pelo campo explícito
`TecnologiaAnalise.modulo_tecnico`. O módulo entrega só o que é da tecnologia
(KPIs, fichas técnicas e o conteúdo técnico da carta); o resto é o shell comum.

Tecnologia nova com relatório próprio (ex.: óleo isolante, ensaios elétricos de
transformador): escolha em `ModuloTecnico` + um objeto com `chave`, `montar(ctx)`,
`textos_carta()`, `paragrafos_carta(rel)` e o conteúdo da carta .docx, registrado
em `MODULOS` — sem mexer no shell. O front tem o registro espelho em
`frontend/src/features/relatorio-inspecao/modulos/index.ts`.
"""
from apps.cadastros.models import ModuloTecnico
from apps.ensaios.relatorio import ModuloEnsaioEletrico, ModuloOleoIsolante

from .inspecao import (
    MEDIA_ACELERACAO,
    MEDIA_TEMPERATURA,
    MEDIA_VELOCIDADE,
    ModuloInspecaoRota,
)
from .termografia import CONSIDERACOES_TERMOGRAFIA, GLOSSARIO_TERMOGRAFIA

VIBRACAO = ModuloInspecaoRota(
    chave=ModuloTecnico.VIBRACAO.value,
    medias=(MEDIA_VELOCIDADE, MEDIA_ACELERACAO),
    tabelas_normativas=("ISO_10816",),
)

# Termografia: glossário (critérios de ΔT por Grau de Risco) e considerações do
# relatório de referência RT.TE-2026.02.12.02307; sem a tabela ISO-10816 de vibração.
TERMOGRAFIA = ModuloInspecaoRota(
    chave=ModuloTecnico.TERMOGRAFIA.value,
    medias=(MEDIA_TEMPERATURA,),
    carta_glossario=GLOSSARIO_TERMOGRAFIA,
    carta_consideracoes=CONSIDERACOES_TERMOGRAFIA,
    # 23 termos não cabem numa A4: 6.1–6.2.4 (215 mm) e 6.3–6.10 (244 mm), medidos.
    carta_quebras_glossario=("6.3",),
)

# Tecnologia sem módulo próprio (Sensitiva, Balanceamento, Qualidade de Energia…):
# continua com o layout aprovado de sempre — tabela ISO-10816 na carta e todas as
# médias que houver (decisão de 24/09/2026: "manter como está").
PADRAO = ModuloInspecaoRota(
    chave="",
    medias=(MEDIA_VELOCIDADE, MEDIA_ACELERACAO, MEDIA_TEMPERATURA),
    tabelas_normativas=("ISO_10816",),
)

# Transformador: fichas por ensaio (apps.ensaios) — relatórios de referência 2025-12_TRF-001.
OLEO_ISOLANTE = ModuloOleoIsolante()
ENSAIO_ELETRICO = ModuloEnsaioEletrico()

MODULOS = {m.chave: m for m in (VIBRACAO, TERMOGRAFIA, OLEO_ISOLANTE, ENSAIO_ELETRICO)}


def modulo_da_tecnologia(tecnologia):
    return MODULOS.get(tecnologia.modulo_tecnico, PADRAO)
