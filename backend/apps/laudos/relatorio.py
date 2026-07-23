"""
Montagem do Relatório Técnico completo (layout do cliente).

Reúne, numa única resposta, tudo que o documento precisa:
    Capa       → contratada, contratante e numeração
    Seção A    → carta ao cliente (datas, instrumentação, normas, glossário)
    Seção C    → relação de equipamentos por Área → Setor, com a condição
    Seção D    → uma Ordem de Serviço Preditiva por anomalia

O PDF é produzido pela impressão do HTML no navegador (Cláusula 12.4 — sem
dependência de biblioteca proprietária de layout).
"""
from apps.cadastros.models import Empresa, Instrumento, Norma
from apps.osp.models import DESCRICAO_GR, OrdemServico

#: Glossário técnico (§6 do relatório) — texto fixo, revisado com o cliente.
GLOSSARIO = [
    ("O.S.P.", "Ordem de Serviço Preditivo gerada para correção de cada anomalia detectada."),
    ("G.R.", "Grau de Risco: determina o prazo de correção das anomalias detectadas."),
    ("GR-1", "Risco eminente — intervenção imediata, prazo máximo de 03 dias. Em casos extremos o inspetor poderá solicitar reparo em caráter de urgência."),
    ("GR-2", "Risco elevado — intervenção pela equipe de manutenção em prazo máximo de 10 dias."),
    ("GR-3", "Risco moderado — intervenção pela equipe de manutenção em prazo máximo de 20 dias."),
    ("GR-4", "Risco baixo — intervenção em parada programada, prazo máximo de 30 dias."),
    ("MP", "Monitoramento Prejudicado: existe obstrução parcial aos equipamentos a serem monitorados."),
    ("NM", "Não Monitorado: existe obstrução total aos equipamentos e/ou risco à integridade física dos trabalhadores."),
    ("OK", "Normalidade Operacional: carga ≥ 70,0%. Os circuitos carregados não apresentam anomalias térmicas."),
    ("PDM", "Parado Devido Manutenção: equipamento parado por intervenção da equipe de manutenção."),
    ("PDP", "Parado Devido Processo: equipamento parado por anormalidade do processo produtivo."),
    ("LA", "Lado Acoplado."),
    ("LOA", "Lado Oposto ao Acoplamento."),
]

#: Tabela ISO 10816-1 — limites de severidade por classe de máquina.
#: Espelha exatamente FAIXAS_ISO_VRMS do motor de regras (apps/coletas/rules.py).
TABELA_ISO_10816 = {
    "titulo": "ISO 10816-1 — Limites de faixa de velocidade e classes de máquina",
    "colunas": [
        "Classe I (< 15 kW)",
        "Classe II (15 a 75 kW)",
        "Classe III (> 75 kW, base rígida)",
        "Classe IV (> 75 kW, base flexível)",
    ],
    "faixas": [
        {"zona": "A", "rotulo": "Bom", "cor": "#22c55e",
         "limites": ["≤ 0,71", "≤ 1,12", "≤ 1,80", "≤ 2,80"]},
        {"zona": "B", "rotulo": "Satisfatório", "cor": "#3b82f6",
         "limites": ["≤ 1,80", "≤ 2,80", "≤ 4,50", "≤ 7,10"]},
        {"zona": "C", "rotulo": "Alerta", "cor": "#eab308",
         "limites": ["≤ 4,50", "≤ 7,10", "≤ 11,20", "≤ 18,00"]},
        {"zona": "D", "rotulo": "Perigo", "cor": "#ef4444",
         "limites": ["> 4,50", "> 7,10", "> 11,20", "> 18,00"]},
    ],
    "unidade": "Velocidade RMS (mm/s)",
}

#: Texto fixo da seção "Definição da Técnica" (§7), por tecnologia.
DEFINICAO_TECNICA = {
    "VIBRACAO": (
        "Uma máquina ideal não produz vibração, pois toda a energia é canalizada para a "
        "execução do trabalho a ser realizado. Na prática, os elementos que compõem as "
        "máquinas interagem entre si e, devido à presença de atrito e à ação de forças "
        "cíclicas, dissipam energia na forma de calor, ruído e vibrações.\n\n"
        "Com o desgaste, a acomodação de fundações, a má utilização e a falta de manutenção, "
        "as máquinas têm suas propriedades dinâmicas alteradas. Todos esses fatores refletem "
        "na diminuição do rendimento e, consequentemente, no aumento do nível de vibração."
    ),
    "TERMOGRAFIA": (
        "A termografia infravermelha detecta anomalias térmicas sem contato e com o "
        "equipamento em operação. A avaliação considera o ΔT entre o ponto inspecionado e "
        "uma referência equivalente, associado à carga do circuito no momento da medição."
    ),
}

#: Fluxo de trabalho em 3 etapas (§7).
FLUXO_TRABALHO = [
    "1ª etapa (contratada): coleta de dados, análise de dados e emissão de laudos.",
    "2ª etapa (contratante): planejamento e execução das correções, retorno das informações.",
    "3ª etapa (contratada): análise das informações retornadas e avaliação de resultados.",
]

CONSIDERACOES = [
    "Os critérios considerados nas análises das anomalias detectadas são técnicos, associados "
    "à experiência do analista, que dará diagnóstico preciso referente à condição na qual o "
    "objeto avaliado está submetido. Cada equipamento tem seu nível de criticidade para a "
    "planta onde está instalado, e isso deve ser levado em consideração pelo controle e "
    "planejamento da manutenção durante a elaboração do plano de manutenções corretivas.",
    "As OSPs emergenciais (GR-1) foram apresentadas, discutidas e tratadas com o planejamento "
    "e controle de manutenção ao término das medições.",
    "Toda anomalia detectada deverá ser corrigida o mais rápido possível: o prazo sugerido "
    "serve apenas como referência, haja vista que a avaliação contratada não é executada em "
    "periodicidade mensal.",
]


def _endereco(obj) -> dict:
    """Bloco de endereço já formatado para o cabeçalho do documento."""
    if obj is None:
        return {}
    return {
        "logradouro": obj.logradouro,
        "numero": obj.numero,
        "complemento": obj.complemento,
        "bairro": obj.bairro,
        "cep": obj.cep,
        "cidade_uf": obj.cidade_uf,
        "formatado": obj.endereco_formatado,
    }


def _equipamentos_da_inspecao(inspecao):
    """Equipamentos medidos na inspeção, sem repetir (vem de 3 tipos de medição)."""
    ids, ordem = set(), []
    for rel in ("medicoes_vibracao", "medicoes_termografia", "medicoes_tecnicas"):
        for m in getattr(inspecao, rel).select_related(
            "equipamento__setor__area", "componente"
        ):
            if m.equipamento_id not in ids:
                ids.add(m.equipamento_id)
                ordem.append(m.equipamento)
    return ordem


def montar_relatorio_tecnico(laudo) -> dict:
    """Monta o payload completo do relatório técnico a partir do laudo."""
    inspecao = laudo.inspecao
    cliente = inspecao.cliente
    empresa = Empresa.objects.ativos().first()
    tipo = inspecao.tipo_analise

    osps = list(
        OrdemServico.objects.filter(inspecao=inspecao)
        .select_related("equipamento__setor__area", "responsavel")
        .order_by("grau_risco", "numero")
    )

    # --- Seção C: equipamentos agrupados por Área → Setor -------------------
    condicao_por_equipamento = {o.equipamento_id: o.grau_risco for o in osps if o.grau_risco}
    agrupado: dict = {}
    for eq in _equipamentos_da_inspecao(inspecao):
        setor = eq.setor
        area = setor.area
        chave_area = area.identificacao
        chave_setor = setor.identificacao
        agrupado.setdefault(chave_area, {}).setdefault(chave_setor, []).append(
            {
                "tag": eq.tag,
                "equipamento": eq.nome,
                # Sem OSP aberta, o equipamento está em normalidade operacional.
                "condicao": condicao_por_equipamento.get(eq.id, "OK").replace("GR", "GR-"),
            }
        )
    secao_c = [
        {
            "area": area,
            "setores": [{"setor": s, "itens": itens} for s, itens in setores.items()],
        }
        for area, setores in agrupado.items()
    ]
    total_equipamentos = sum(
        len(i["itens"]) for a in secao_c for i in a["setores"]
    )

    # --- Instrumentação efetivamente utilizada na inspeção ------------------
    instrumento_ids = set()
    for rel in ("medicoes_vibracao", "medicoes_termografia", "medicoes_tecnicas"):
        instrumento_ids.update(
            getattr(inspecao, rel).exclude(instrumento=None).values_list("instrumento_id", flat=True)
        )
    instrumentos = Instrumento.objects.filter(id__in=instrumento_ids) or Instrumento.objects.ativos()[:1]

    # --- Normas da tecnologia analisada -------------------------------------
    normas = Norma.objects.ativos().prefetch_related("tecnologias")

    return {
        "laudo": {
            "numero": laudo.numero,
            "titulo": laudo.titulo,
            "versao": laudo.versao,
            "status": laudo.status,
            "data_medicao_campo": laudo.data_medicao_campo,
            "data_upload_osps": laudo.data_upload_osps,
            "data_upload_relatorio": laudo.data_upload_relatorio,
            "diagnostico": laudo.diagnostico,
            "recomendacoes": laudo.recomendacoes,
            "conclusao": laudo.conclusao,
            "responsavel": laudo.responsavel.nome,
            "responsavel_cargo": laudo.responsavel.cargo or "Analista em Manutenção Preditiva",
            "responsavel_conselho": laudo.responsavel.conselho_classe,
        },
        "inspecao": {
            "id": inspecao.id,
            "tipo_analise": tipo,
            "tipo_analise_display": inspecao.get_tipo_analise_display(),
            "data": inspecao.data,
        },
        "contratada": {
            "nome": empresa.nome if empresa else "",
            "cnpj": empresa.cnpj if empresa else "",
            "endereco": _endereco(empresa),
            "contato": empresa.contato_gestor if empresa else "",
        },
        "contratante": {
            "nome": cliente.nome,
            "nome_fantasia": cliente.nome_fantasia,
            "cnpj": cliente.cnpj,
            "unidade_negocio": cliente.unidade_negocio,
            "endereco": _endereco(cliente),
            "contato_gestor": cliente.contato_gestor,
            "departamento": cliente.departamento,
            "email": cliente.email,
            "telefone": cliente.telefone,
        },
        "instrumentacao": [
            {
                "tipo": i.tipo,
                "marca": i.marca,
                "modelo": i.modelo,
                "numero_serie": i.numero_serie,
                "data_ultima_calibracao": i.data_ultima_calibracao,
                "validade": i.get_periodicidade_calibracao_display(),
                "proxima_calibracao": i.proxima_calibracao,
                "entidade_calibracao": i.entidade_calibracao,
                "software_analise": i.software_analise,
            }
            for i in instrumentos
        ],
        "normas": [
            {"codigo": n.codigo, "titulo": n.nome, "orgao": n.orgao}
            for n in normas
        ],
        "tabela_iso": TABELA_ISO_10816 if tipo == "VIBRACAO" else None,
        "definicao_tecnica": DEFINICAO_TECNICA.get(tipo, ""),
        "fluxo_trabalho": FLUXO_TRABALHO,
        "glossario": [{"sigla": s, "descricao": d} for s, d in GLOSSARIO],
        "consideracoes": CONSIDERACOES,
        "secao_c": {"total_equipamentos": total_equipamentos, "areas": secao_c},
        "secao_d": [
            {
                "numero": o.numero,
                "grau_risco": (o.grau_risco or "").replace("GR", "GR-"),
                "grau_risco_descricao": DESCRICAO_GR.get(o.grau_risco, ""),
                "prazo_dias": o.prazo_dias,
                "area": o.equipamento.setor.area.identificacao,
                "setor": o.equipamento.setor.identificacao,
                "tag": o.equipamento.tag,
                "equipamento": o.equipamento.nome,
                "componente": o.componente,
                "anomalia": o.anomalia,
                "recomendacao": o.recomendacao,
                "observacao": o.observacao,
                "amplitude_velocidade": o.amplitude_velocidade,
                "amplitude_aceleracao": o.amplitude_aceleracao,
                "avaliacao": {
                    "linhas": [
                        {
                            "rotulo": "Mão de Obra (h)",
                            "pred_qtd": o.pred_mao_obra_h, "pred_valor": o.pred_mao_obra_valor,
                            "emerg_qtd": o.emerg_mao_obra_h, "emerg_valor": o.emerg_mao_obra_valor,
                        },
                        {
                            "rotulo": "Serv. Terceirizado (h)",
                            "pred_qtd": o.pred_terceirizado_h, "pred_valor": o.pred_terceirizado_valor,
                            "emerg_qtd": o.emerg_terceirizado_h, "emerg_valor": o.emerg_terceirizado_valor,
                        },
                        {
                            "rotulo": "Material Reparo (R$)",
                            "pred_qtd": None, "pred_valor": o.pred_material_valor,
                            "emerg_qtd": None, "emerg_valor": o.emerg_material_valor,
                        },
                        {
                            "rotulo": "Produção (h/ton)",
                            "pred_qtd": o.pred_producao_h, "pred_valor": o.pred_producao_valor,
                            "emerg_qtd": o.emerg_producao_h, "emerg_valor": o.emerg_producao_valor,
                        },
                        {
                            "rotulo": "Outros (R$)",
                            "pred_qtd": None, "pred_valor": o.pred_outros_valor,
                            "emerg_qtd": None, "emerg_valor": o.emerg_outros_valor,
                        },
                    ],
                    "total_preditiva": o.total_preditiva,
                    "total_emergencial": o.total_emergencial,
                    "retorno_investimento": o.retorno_investimento,
                },
                "planejamento": {"data": o.planejado_em, "responsavel": getattr(o.planejado_por, "nome", "")},
                "corretiva": {"data": o.executado_em, "responsavel": getattr(o.executado_por, "nome", "")},
                "finalizacao": {"data": o.finalizada_em, "responsavel": getattr(o.finalizado_por, "nome", "")},
            }
            for o in osps
        ],
    }
