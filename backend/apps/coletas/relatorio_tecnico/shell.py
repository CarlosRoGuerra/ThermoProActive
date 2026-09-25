"""
Shell do relatório técnico — a parte IGUAL para qualquer tecnologia.

Capa, Carta ao Cliente, Relação de Equipamentos Monitorados, paginação e PDF leem
só o que é montado aqui (`cabecalho` e `secao_c`). KPIs e fichas técnicas são do
módulo da tecnologia (ver `modulos.py`) — o shell nunca olha para eles.
"""
from dataclasses import dataclass

from apps.cadastros.models import Condicao, Empresa, Norma

from ..models import ItemInspecao


def rotulo_condicao(cond) -> str:
    return (cond.sigla or cond.nome) if cond else "—"


@dataclass
class ContextoRelatorio:
    """O que o shell já carregou e os módulos reaproveitam, sem consultar de novo."""

    rel: object
    request: object
    # Itens da rota na ordem do documento: Área → Setor → TAG → linha.
    itens: list
    equipamentos_ids: set


def carregar_contexto(rel, request) -> ContextoRelatorio:
    itens = list(
        ItemInspecao.objects.filter(carregamento__relatorio=rel)
        .select_related("equipamento__setor__area", "condicao")
        .prefetch_related("achados__condicao", "achados__tipo_componente")
        .order_by("equipamento__setor__area__nome", "equipamento__setor__nome",
                  "equipamento__tag", "ordem")
    )
    return ContextoRelatorio(
        rel=rel, request=request, itens=itens,
        equipamentos_ids={item.equipamento_id for item in itens},
    )


def _endereco_em_duas_linhas(o) -> tuple[str, str]:
    """Logradouro, nº – bairro | CEP – cidade/UF (capa e papel timbrado)."""
    linha1 = " – ".join(p for p in [
        ", ".join(x for x in [o.logradouro, o.numero] if x),
        o.bairro,
    ] if p)
    linha2 = " – ".join(p for p in [o.cep, o.cidade_uf] if p)
    return linha1, linha2


def montar_cabecalho(rel, request, instrumentos_extras=()) -> dict:
    """
    Prestador, cliente, número, tecnologia, datas, equipe, instrumentação e normas.
    `instrumentos_extras`: instrumentação que o módulo usa além da dos carregamentos
    (ex.: um instrumento por ensaio elétrico).
    """
    cliente = rel.cliente
    # Prestador de serviço (contratada) — papel timbrado do relatório.
    prestador = Empresa.objects.ativos().order_by("id").first()

    carregs = list(rel.carregamentos.select_related("instrumento", "analista"))
    analistas_por_id = {c.analista_id: c.analista for c in carregs if c.analista_id}
    analistas = [
        {
            "nome": u.nome,
            "assinatura": (
                request.build_absolute_uri(u.assinatura_digital.url) if u.assinatura_digital else None
            ),
        }
        for u in sorted(analistas_por_id.values(), key=lambda u: u.nome)
    ]

    # Instrumentação com dados de calibração (atrelados ao ID do instrumento).
    instrumentos, vistos = [], set()
    for ins in [c.instrumento for c in carregs] + list(instrumentos_extras):
        if ins and ins.id not in vistos:
            vistos.add(ins.id)
            instrumentos.append({
                "tipo": ins.tipo, "marca": ins.marca, "modelo": ins.modelo,
                "numero_serie": ins.numero_serie,
                "data_ultima_calibracao": ins.data_ultima_calibracao,
                "proxima_calibracao": ins.proxima_calibracao,
                "periodicidade": ins.get_periodicidade_calibracao_display(),
                "entidade_calibracao": ins.entidade_calibracao,
                "software_analise": ins.software_analise,
            })

    # Normas ligadas à tecnologia do relatório.
    normas = [
        {"codigo": n.codigo, "nome": n.nome, "orgao": n.orgao}
        for n in Norma.objects.ativos().filter(tecnologias=rel.tecnologia).order_by("codigo")
    ]

    # Glossário: TODAS as condições cadastradas (todos os GRs, OK, PDP…) — é uma
    # referência para o leitor, não só as usadas neste relatório. Descrição vem
    # do cadastro "Condição do Equipamento". Ordem alfabética pela sigla, o que
    # naturalmente coloca os GRs primeiro (G antes de I, M, N, O, P).
    glossario = sorted(
        (
            {"sigla": c.sigla or c.nome, "termo": c.nome, "descricao": c.descricao or c.nome}
            for c in Condicao.objects.ativos()
        ),
        key=lambda g: g["sigla"].upper(),
    )

    cli_l1, cli_l2 = _endereco_em_duas_linhas(cliente)
    dados_prestador = None
    if prestador:
        end_l1, end_l2 = _endereco_em_duas_linhas(prestador)
        dados_prestador = {
            "nome": prestador.nome,
            "cnpj": prestador.cnpj,
            "inscricao_estadual": prestador.inscricao_estadual,
            "endereco": prestador.endereco_formatado,
            "endereco_linha1": end_l1,
            "endereco_linha2": end_l2,
            "cidade_uf": prestador.cidade_uf,
            "email": prestador.email,
            "telefone": prestador.telefone,
            "site": prestador.site,
            "logomarca": request.build_absolute_uri(prestador.logomarca.url) if prestador.logomarca else None,
        }

    return {
        "prestador": dados_prestador,
        "empresa": cliente.nome,
        "nome_fantasia": cliente.nome_fantasia,
        "cnpj": cliente.cnpj,
        "endereco": cliente.endereco_formatado,
        "endereco_linha1": cli_l1,
        "endereco_linha2": cli_l2,
        "cidade_uf": cliente.cidade_uf,
        "contato": cliente.contato_gestor,
        "departamento": cliente.departamento,
        "logomarca": request.build_absolute_uri(cliente.logomarca.url) if cliente.logomarca else None,
        "numero": rel.numero,
        "tecnologia": rel.tecnologia.nome,
        "tecnologia_imagem": (
            request.build_absolute_uri(rel.tecnologia.imagem.url) if rel.tecnologia.imagem else None
        ),
        "definicao_tecnica": rel.tecnologia.definicao_tecnica,
        "definicao_fluxo_trabalho": rel.tecnologia.definicao_fluxo_trabalho,
        "definicao_legenda_imagem": rel.tecnologia.definicao_legenda_imagem,
        "pontos_medicao_imagem": (
            request.build_absolute_uri(rel.tecnologia.imagem_pontos_medicao.url)
            if rel.tecnologia.imagem_pontos_medicao else None
        ),
        "analistas": analistas,
        "data_inicio": rel.data_inicio,
        "data_termino": rel.data_termino,
        "data_finalizacao": rel.data_finalizacao,
        "instrumentos": instrumentos,
        "normas": normas,
        "glossario": glossario,
        "consideracoes_finais": rel.consideracoes_finais,
    }


def montar_secao_c(ctx: ContextoRelatorio) -> dict:
    """
    Relação de Equipamentos Monitorados, por Área → Setor.

    A lista é de EQUIPAMENTOS: 1 linha por item da rota com a condição do
    equipamento. Os componentes aparecem nas fichas técnicas, não aqui — assim o
    "Total de equipamentos" bate com o nº de linhas (gabarito).
    """
    grupos: dict = {}
    total = 0
    for item in ctx.itens:
        eq = item.equipamento
        setor = eq.setor
        area = setor.area if setor else None
        chave = (area.nome if area else "—", setor.nome if setor else "—")
        grupos.setdefault(chave, []).append(
            {"tag": eq.tag, "equipamento": eq.nome, "condicao": rotulo_condicao(item.condicao)}
        )
        total += 1
    return {
        "total": total,
        # Equipamentos distintos ("adicionar linha" repete o equipamento na rota).
        "equip_monitorados": len(ctx.equipamentos_ids),
        "grupos": [{"area": a, "setor": s, "linhas": linhas} for (a, s), linhas in grupos.items()],
    }
