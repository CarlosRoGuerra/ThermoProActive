"""
Filtros comuns a relatórios (2.9) e painéis (2.8.1.3.2) — validados no SERVIDOR.

Regras:
* Escopo de segurança primeiro (`escopo_cliente`, falha fechada), filtro depois:
  `?cliente=<outro>` vindo do Portal nunca amplia nada, só esvazia.
* Filtro malformado é ERRO (400), nunca ignorado em silêncio — um relatório
  "filtrado" que na verdade trouxe tudo é pior do que nenhum relatório.
* Período é inclusivo nas duas pontas e usa a data do fato de cada entidade
  (ver `CAMPOS_DATA` e docs/16).
"""
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime

from django.db.models import Exists, OuterRef, Q

from apps.coletas.views import escopo_cliente


class FiltroInvalido(ValueError):
    def __init__(self, erros: dict):
        super().__init__(erros)
        self.erros = erros


@dataclass(frozen=True)
class Filtros:
    cliente: int | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
    area: int | None = None
    setor: int | None = None
    equipamento: int | None = None

    @property
    def recorte_de_parque(self) -> bool:
        return bool(self.area or self.setor or self.equipamento)

    def sem_parque(self) -> "Filtros":
        """Para entidades sem equipamento (cliente, inspeção, laudo) — o recorte vai à parte."""
        return replace(self, area=None, setor=None, equipamento=None)

    def como_dict(self) -> dict:
        return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in asdict(self).items()}


def ler_filtros(params) -> Filtros:
    erros, valores = {}, {}
    for nome in ("cliente", "area", "setor", "equipamento"):
        bruto = (params.get(nome) or "").strip()
        if not bruto:
            continue
        if not bruto.isdigit():
            erros[nome] = "Informe o identificador numérico."
        else:
            valores[nome] = int(bruto)
    for nome in ("data_inicio", "data_fim"):
        bruto = (params.get(nome) or "").strip()
        if not bruto:
            continue
        try:
            valores[nome] = datetime.strptime(bruto, "%Y-%m-%d").date()
        except ValueError:
            erros[nome] = "Use o formato AAAA-MM-DD."
    if not erros and valores.get("data_inicio") and valores.get("data_fim"):
        if valores["data_inicio"] > valores["data_fim"]:
            erros["data_fim"] = "A data final é anterior à inicial."
    if erros:
        raise FiltroInvalido(erros)
    return Filtros(**valores)


def aplicar(qs, user, f: Filtros, *, cliente: str, data: str | None = None, equipamento: str | None = None):
    """
    Escopo + filtros para um queryset.

    `cliente`: caminho ORM até o cliente. `data`: caminho do campo de data (ou
    None se a entidade não tem período). `equipamento`: caminho até o
    equipamento (para área/setor/equipamento) — obrigatório quando houver
    recorte de parque, para não ignorar o filtro em silêncio.
    """
    qs = escopo_cliente(qs, user, cliente)
    if f.cliente:
        qs = qs.filter(**{cliente: f.cliente})
    if data:
        if f.data_inicio:
            qs = qs.filter(**{f"{data}__gte": f.data_inicio})
        if f.data_fim:
            qs = qs.filter(**{f"{data}__lte": f.data_fim})
    if f.recorte_de_parque:
        if not equipamento:
            raise ValueError("recorte de parque sem caminho até o equipamento")
        qs = qs.filter(q_parque(f, equipamento))
    return qs


def q_parque(f: Filtros, caminho: str) -> Q:
    q = Q()
    if f.equipamento:
        q &= Q(**{caminho: f.equipamento})
    if f.setor:
        q &= Q(**{f"{caminho}__setor": f.setor})
    if f.area:
        q &= Q(**{f"{caminho}__setor__area": f.area})
    return q


def inspecoes(user, f: Filtros, base=None):
    """
    Inspeções no escopo. A inspeção não tem equipamento: com recorte de parque,
    entram as que têm ao menos uma medição de equipamento do recorte.
    """
    from apps.coletas.models import Inspecao, MedicaoTecnica, MedicaoTermografia, MedicaoVibracao

    qs = aplicar(base if base is not None else Inspecao.objects.ativos(), user, f.sem_parque(),
                 cliente="cliente", data="data")
    if f.recorte_de_parque:
        alguma = Q()
        for modelo in (MedicaoVibracao, MedicaoTermografia, MedicaoTecnica):
            alguma |= Exists(
                modelo.objects.filter(q_parque(f, "equipamento"), inspecao=OuterRef("pk"))
            )
        qs = qs.filter(alguma)
    return qs


def medicoes(user, f: Filtros, modelo, *, periodo=True):
    """Medições do escopo; o período é a data da INSPEÇÃO (mesma base dos relatórios)."""
    return aplicar(
        modelo.objects.all(), user, f, cliente="inspecao__cliente",
        data="inspecao__data" if periodo else None, equipamento="equipamento",
    )


def osps(user, f: Filtros, *, periodo=True):
    """OSPs do escopo (canceladas incluídas — quem chama decide). Período = abertura."""
    from apps.osp.models import OrdemServico

    return aplicar(
        OrdemServico.objects.all(), user, f, cliente="cliente",
        data="criado_em__date" if periodo else None, equipamento="equipamento",
    )


def equipamentos(user, f: Filtros):
    """Equipamentos ATIVOS do escopo, com o recorte de parque aplicado."""
    from apps.cadastros.models import Equipamento

    qs = escopo_cliente(Equipamento.objects.ativos(), user, "setor__area__cliente")
    if f.cliente:
        qs = qs.filter(setor__area__cliente=f.cliente)
    if f.equipamento:
        qs = qs.filter(pk=f.equipamento)
    if f.setor:
        qs = qs.filter(setor=f.setor)
    if f.area:
        qs = qs.filter(setor__area=f.area)
    return qs


def laudos(user, f: Filtros, *, data="data_emissao__date"):
    """Laudos no escopo — mesma regra do `LaudoViewSet` (cliente só vê os emitidos)."""
    from apps.laudos.models import Laudo, StatusLaudo

    qs = Laudo.objects.all()
    if user.is_cliente:
        if not user.cliente_id:
            return qs.none()
        qs = qs.filter(Q(status=StatusLaudo.EMITIDO) | Q(status=StatusLaudo.CANCELADO, data_emissao__isnull=False))
        qs = qs.filter(Laudo.q_do_cliente(user.cliente_id))
    if f.cliente:
        qs = qs.filter(Laudo.q_do_cliente(f.cliente))
    if data:
        if f.data_inicio:
            qs = qs.filter(**{f"{data}__gte": f.data_inicio})
        if f.data_fim:
            qs = qs.filter(**{f"{data}__lte": f.data_fim})
    return qs
