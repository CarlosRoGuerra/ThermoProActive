"""
Registro dos módulos técnicos do relatório.

Cada tecnologia aponta para um módulo pelo campo explícito
`TecnologiaAnalise.modulo_tecnico`. O módulo entrega só o que é da tecnologia
(KPIs, fichas técnicas e o conteúdo técnico da carta); o resto é o shell comum.

Não existe módulo "padrão". Uma tecnologia:
  - com módulo implementado → usa o seu módulo;
  - configurada como `INSPECAO_GENERICA` → inspeção por rota sem medições
    específicas (sem tabela de vibração, sem amplitudes);
  - sem módulo configurado, ou com um módulo planejado ainda sem implementação
    → `ModuloIndisponivel`, com o motivo. Nunca cai no layout de outra técnica.

Tecnologia nova com relatório próprio: escolha em `ModuloTecnico` + um objeto
com `chave`, `montar(ctx)`, `textos_carta()`, `paragrafos_carta(rel)` e o
conteúdo da carta .docx, registrado em `MODULOS` — sem mexer no shell. O front
tem o registro espelho em `frontend/src/features/relatorio-inspecao/modulos/index.ts`.
"""
from apps.cadastros.models import MODULOS_PLANEJADOS, ModuloTecnico
from apps.ensaios.relatorio import ModuloEnsaioEletrico, ModuloOleoIsolante
from apps.ensaios.relatorio_fluidos import ModuloFluidoLubrificante
from apps.ensaios.relatorio_subestacao import MODULO_CS, MODULO_DJ, MODULO_RP, MODULO_TC, MODULO_TP

from .espessura import MODULO_ESPESSURA
from .motor_rxi import MODULO_MOTOR_RXI
from .alinhamento import MODULO_ALINHAMENTO_EIXOS, MODULO_ALINHAMENTO_POLIAS
from .qualidade_energia import MODULO_QUALIDADE_ENERGIA
from .termografia_sistemas import MODULO_TERMO_PROCESSOS, MODULO_TERMOGRAFIA_MECANICA
from .ultrassom import MODULO_ULTRASSOM
from .generico import CONSIDERACOES_GENERICAS, GLOSSARIO_GENERICO
from .inspecao import (
    MEDIA_ACELERACAO,
    MEDIA_TEMPERATURA,
    MEDIA_VELOCIDADE,
    ModuloInspecaoRota,
)
from .termografia import CONSIDERACOES_TERMOGRAFIA, GLOSSARIO_TERMOGRAFIA


class ModuloIndisponivel(Exception):
    """A tecnologia não tem um módulo de relatório que possa ser usado."""

    codigo = "modulo_indisponivel"

    def __init__(self, tecnologia, mensagem):
        super().__init__(mensagem)
        self.tecnologia = tecnologia
        self.mensagem = mensagem


class ModuloNaoConfigurado(ModuloIndisponivel):
    codigo = "modulo_nao_configurado"


class ModuloNaoImplementado(ModuloIndisponivel):
    codigo = "modulo_nao_implementado"


VIBRACAO = ModuloInspecaoRota(
    chave=ModuloTecnico.VIBRACAO.value,
    medias=(MEDIA_VELOCIDADE, MEDIA_ACELERACAO),
    tabelas_normativas=("ISO_10816",),
)

# Balanceamento: o veredito de cada ponto é a zona de severidade de vibração, por
# isso a carta tem a tabela de severidade. Mesmo layout de antes da separação
# (era o "padrão"), agora declarado.
BALANCEAMENTO = ModuloInspecaoRota(
    chave=ModuloTecnico.BALANCEAMENTO.value,
    medias=(MEDIA_VELOCIDADE, MEDIA_ACELERACAO, MEDIA_TEMPERATURA),
    tabelas_normativas=("ISO_10816",),
)

# Termografia em sistemas elétricos: segue o relatório de referência do cliente
# (RT.TE-2026.05.18.02326) — glossário com os critérios de ΔT por Grau de Risco e o
# Fluxo de Trabalho (6.11), Considerações como item 7, instrumentação numerada, data
# "Upload das OSP´s" e Seção C por nome do equipamento. Sem a tabela ISO de vibração.
TERMOGRAFIA = ModuloInspecaoRota(
    chave=ModuloTecnico.TERMOGRAFIA.value,
    medias=(MEDIA_TEMPERATURA,),
    carta_glossario=GLOSSARIO_TERMOGRAFIA,
    carta_consideracoes=CONSIDERACOES_TERMOGRAFIA,
    # 31 termos não cabem numa A4 (cada folha da carta é fixa): três folhas, medidas.
    carta_quebras_glossario=("6.3", "6.8"),
    carta_definicao_tecnica=False,
    carta_instrumentacao_numerada=True,
    carta_data_osps=True,
    secao_c_ordem="nome",
)

# Inspeção genérica (ex.: Análise Sensitiva Sensorial): OSPs sem bloco de medição,
# sem tabela normativa e com glossário/considerações neutros.
INSPECAO_GENERICA = ModuloInspecaoRota(
    chave=ModuloTecnico.INSPECAO_GENERICA.value,
    carta_glossario=GLOSSARIO_GENERICO,
    carta_consideracoes=CONSIDERACOES_GENERICAS,
)

# Transformador: fichas por ensaio (apps.ensaios) — relatórios de referência 2025-12_TRF-001.
OLEO_ISOLANTE = ModuloOleoIsolante()
ENSAIO_ELETRICO = ModuloEnsaioEletrico()
# Fluidos lubrificantes e hidráulicos: fichas FQ, EF e CP por amostra (apps.ensaios).
FLUIDO_LUBRIFICANTE = ModuloFluidoLubrificante()

MODULOS = {
    m.chave: m
    for m in (VIBRACAO, BALANCEAMENTO, TERMOGRAFIA, INSPECAO_GENERICA, MODULO_ESPESSURA, MODULO_MOTOR_RXI,
              MODULO_ULTRASSOM, MODULO_QUALIDADE_ENERGIA, MODULO_TERMOGRAFIA_MECANICA, MODULO_TERMO_PROCESSOS,
              MODULO_ALINHAMENTO_EIXOS, MODULO_ALINHAMENTO_POLIAS,
              OLEO_ISOLANTE, ENSAIO_ELETRICO, FLUIDO_LUBRIFICANTE,
              MODULO_TC, MODULO_TP, MODULO_DJ, MODULO_CS, MODULO_RP)
}


def modulo_da_tecnologia(tecnologia):
    chave = tecnologia.modulo_tecnico
    if chave in MODULOS:
        return MODULOS[chave]
    if chave in MODULOS_PLANEJADOS:
        raise ModuloNaoImplementado(
            tecnologia,
            f"O relatório de «{tecnologia.get_modulo_tecnico_display()}» ainda não foi implementado. "
            f"A tecnologia «{tecnologia.nome}» não usa o layout de outra técnica no lugar.",
        )
    if not chave:
        raise ModuloNaoConfigurado(
            tecnologia,
            f"A tecnologia «{tecnologia.nome}» não tem módulo técnico configurado. Escolha o módulo em "
            "Cadastros → Tecnologias de análise (\"Inspeção genérica\" para inspeção sem medições específicas).",
        )
    raise ModuloNaoImplementado(tecnologia, f"Módulo técnico desconhecido: «{chave}».")
