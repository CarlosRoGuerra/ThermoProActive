"""
Relatório técnico (dossiê): shell comum + módulo técnico da tecnologia.

    CAPA → CARTA AO CLIENTE → KPI → EQUIPAMENTOS MONITORADOS → FICHAS TÉCNICAS → CONCLUSÕES
    └──────────────── shell (shell.py) ────────────────┘   └── módulo (modulos.py) ──┘

Payload do endpoint `/relatorios-inspecao/{id}/dossie/`:
  - `modulo`: chave do módulo da tecnologia ("" = layout padrão);
  - `cabecalho`, `secao_c`: shell — iguais para qualquer tecnologia;
  - `carta`: textos técnicos da carta que o módulo fornece (seções, glossário,
    considerações) — a mesma fonte da carta .docx;
  - demais chaves: do módulo (na inspeção por rota, `secao_b` e `secao_d`).
"""
from .modulos import modulo_da_tecnologia
from .shell import carregar_contexto, montar_cabecalho, montar_secao_c


def montar_dossie(rel, request) -> dict:
    modulo = modulo_da_tecnologia(rel.tecnologia)
    ctx = carregar_contexto(rel, request)
    tecnico = modulo.montar(ctx)
    carta = modulo.textos_carta(tecnico)
    tecnico.pop("resumo", None)  # já está na carta (parágrafo do item 7)
    return {
        "modulo": modulo.chave,
        "cabecalho": montar_cabecalho(rel, request, modulo.instrumentos_adicionais(ctx)),
        "secao_c": montar_secao_c(ctx),
        "carta": carta,
        **tecnico,
    }
