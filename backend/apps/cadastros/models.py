"""
Cadastros — Anexo I, item 2.2 e estrutura de banco item 3.1.

Hierarquia de localização (item 2.2.1.15–17):
    Cliente → Área → Setor → Equipamento → Componente
"""
from django.db import models

from apps.core.models import BaseModel


class Empresa(BaseModel):
    """Empresa CONTRATADA (prestadora) — Anexo I 3.1.1."""

    nome = models.CharField("Nome da empresa", max_length=160)
    cnpj = models.CharField("CNPJ", max_length=18, unique=True)
    cidade_uf = models.CharField("Cidade/UF", max_length=80, blank=True)
    cep = models.CharField("CEP", max_length=10, blank=True)
    endereco = models.CharField("Endereço", max_length=200, blank=True)
    contato_gestor = models.CharField("Contato gestor", max_length=120, blank=True)
    departamento = models.CharField("Departamento", max_length=120, blank=True)
    logomarca = models.ImageField("Logomarca", upload_to="logos/empresas/", null=True, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Empresa (contratada)"
        verbose_name_plural = "Empresas (contratadas)"

    def __str__(self):
        return self.nome


class Cliente(BaseModel):
    """Empresa CONTRATANTE (cliente) — Anexo I 3.1.3."""

    nome = models.CharField("Nome da empresa", max_length=160)
    cnpj = models.CharField("CNPJ", max_length=18, unique=True)
    unidade_negocio = models.CharField("Unidade de negócio", max_length=120, blank=True)
    cidade_uf = models.CharField("Cidade/UF", max_length=80, blank=True)
    cep = models.CharField("CEP", max_length=10, blank=True)
    endereco = models.CharField("Endereço", max_length=200, blank=True)
    contato_gestor = models.CharField("Contato gestor", max_length=120, blank=True)
    departamento = models.CharField("Departamento", max_length=120, blank=True)
    logomarca = models.ImageField("Logomarca", upload_to="logos/clientes/", null=True, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Cliente (contratante)"
        verbose_name_plural = "Clientes (contratantes)"

    def __str__(self):
        return self.nome


class Area(BaseModel):
    """Local de inspeção [Área] — item 2.2.1.15."""

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="areas")
    nome = models.CharField("Área", max_length=120)

    class Meta(BaseModel.Meta):
        verbose_name = "Área"
        verbose_name_plural = "Áreas"
        unique_together = [("cliente", "nome")]

    def __str__(self):
        return f"{self.cliente} / {self.nome}"


class Setor(BaseModel):
    """Local de inspeção [Setor] — item 2.2.1.16."""

    area = models.ForeignKey(Area, on_delete=models.CASCADE, related_name="setores")
    nome = models.CharField("Setor", max_length=120)

    class Meta(BaseModel.Meta):
        verbose_name = "Setor"
        verbose_name_plural = "Setores"
        unique_together = [("area", "nome")]

    def __str__(self):
        return f"{self.area.nome} / {self.nome}"


class ClasseISO(models.TextChoices):
    """Classe da máquina p/ severidade de vibração (ISO 10816/20816)."""

    I = "I", "Classe I (≤15 kW)"
    II = "II", "Classe II (15–75 kW)"
    III = "III", "Classe III (base rígida)"
    IV = "IV", "Classe IV (base flexível)"


class Equipamento(BaseModel):
    """Local de inspeção [Equipamento] / máquina — itens 2.2.1.17 e 3.1.8."""

    setor = models.ForeignKey(Setor, on_delete=models.PROTECT, related_name="equipamentos")
    tag = models.CharField("TAG", max_length=60, help_text="Identificação no campo (ex.: BBA-101)")
    nome = models.CharField("Nome/Descrição", max_length=160)
    tipo = models.CharField("Tipo de equipamento", max_length=80, blank=True)
    fabricante = models.CharField("Fabricante", max_length=80, blank=True)
    modelo = models.CharField("Modelo", max_length=80, blank=True)
    numero_serie = models.CharField("Número de série", max_length=80, blank=True)
    potencia_kw = models.DecimalField("Potência (kW)", max_digits=8, decimal_places=2, null=True, blank=True)
    rotacao_nominal_rpm = models.PositiveIntegerField("Rotação nominal (RPM)", null=True, blank=True)
    classe_iso = models.CharField(
        "Classe ISO (vibração)", max_length=3, choices=ClasseISO.choices,
        default=ClasseISO.II, help_text="Define os limiares de severidade da análise de vibração.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Equipamento"
        verbose_name_plural = "Equipamentos"
        unique_together = [("setor", "tag")]

    def __str__(self):
        return f"{self.tag} — {self.nome}"


class Componente(BaseModel):
    """Componente/ponto do equipamento (mancal, motor, bomba) — item 3.1.13."""

    equipamento = models.ForeignKey(Equipamento, on_delete=models.CASCADE, related_name="componentes")
    nome = models.CharField("Componente", max_length=120, help_text="Ex.: Mancal LA, Mancal LOA")

    class Meta(BaseModel.Meta):
        verbose_name = "Componente"
        verbose_name_plural = "Componentes"

    def __str__(self):
        return f"{self.equipamento.tag} / {self.nome}"


class Instrumento(BaseModel):
    """Instrumentação/coletor — itens 2.2.1.4 e 3.1.10 (com controle de calibração)."""

    tipo = models.CharField("Tipo de instrumento", max_length=80)
    marca = models.CharField("Marca", max_length=80, blank=True)
    modelo = models.CharField("Modelo", max_length=80, blank=True)
    numero_serie = models.CharField("Número de série", max_length=80, blank=True)
    data_ultima_calibracao = models.DateField("Última calibração", null=True, blank=True)
    entidade_calibracao = models.CharField("Entidade de calibração", max_length=120, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Instrumento"
        verbose_name_plural = "Instrumentos"

    def __str__(self):
        return f"{self.tipo} {self.marca} {self.modelo}".strip()


# =============================================================================
# Catálogos / tabelas de referência — Anexo I 2.2.1.5 a 2.2.1.14 e 2.2.1.18.
# Tabelas simples (nome + descrição) usadas para padronizar a operação e
# alimentar os selects do sistema. Mantidas parametrizáveis pelo cliente
# (sem regra "escondida" em código — alinhado à Cláusula 12.4).
# =============================================================================


class Catalogo(BaseModel):
    """Base abstrata para tabelas de referência simples."""

    nome = models.CharField("Nome", max_length=120)
    descricao = models.TextField("Descrição", blank=True)

    class Meta(BaseModel.Meta):
        abstract = True
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Norma(Catalogo):
    """Normas técnicas (NBR/ISO/IEEE) — item 2.2.1.5."""

    codigo = models.CharField("Código", max_length=40, help_text="Ex.: NBR 10816, ISO 20816")
    orgao = models.CharField("Órgão", max_length=40, blank=True, help_text="ABNT, ISO, IEEE…")

    class Meta(Catalogo.Meta):
        verbose_name = "Norma"
        verbose_name_plural = "Normas (NBRs)"

    def __str__(self):
        return f"{self.codigo} — {self.nome}" if self.codigo else self.nome


class TecnologiaAnalise(Catalogo):
    """Tecnologias/Tipos de análise — item 2.2.1.6."""

    sigla = models.CharField("Sigla", max_length=20, blank=True)

    class Meta(Catalogo.Meta):
        verbose_name = "Tecnologia/Tipo de análise"
        verbose_name_plural = "Tecnologias/Tipos de análise"


class TipoEquipamento(Catalogo):
    """Tipo de equipamento/máquina — item 2.2.1.7."""

    class Meta(Catalogo.Meta):
        verbose_name = "Tipo de equipamento"
        verbose_name_plural = "Tipos de equipamento"


class ClassificacaoInspecao(Catalogo):
    """Classificação do tipo de inspeção — item 2.2.1.14."""

    class Meta(Catalogo.Meta):
        verbose_name = "Classificação de inspeção"
        verbose_name_plural = "Classificações de inspeção"


class TipoInspecao(Catalogo):
    """Tipo de inspeção — item 2.2.1.8."""

    classificacao = models.ForeignKey(
        ClassificacaoInspecao, on_delete=models.SET_NULL, null=True, blank=True, related_name="tipos"
    )

    class Meta(Catalogo.Meta):
        verbose_name = "Tipo de inspeção"
        verbose_name_plural = "Tipos de inspeção"


class FalhaRecorrente(Catalogo):
    """Falhas recorrentes — item 2.2.1.8."""

    class Meta(Catalogo.Meta):
        verbose_name = "Falha recorrente"
        verbose_name_plural = "Falhas recorrentes"


class TipoComponente(Catalogo):
    """Tipo de componente — item 2.2.1.9."""

    class Meta(Catalogo.Meta):
        verbose_name = "Tipo de componente"
        verbose_name_plural = "Tipos de componente"


class TipoAnomalia(Catalogo):
    """Tipo de anomalia — item 2.2.1.10."""

    class Meta(Catalogo.Meta):
        verbose_name = "Tipo de anomalia"
        verbose_name_plural = "Tipos de anomalia"


class TipoRecomendacao(Catalogo):
    """Tipo de recomendação — item 2.2.1.11."""

    class Meta(Catalogo.Meta):
        verbose_name = "Tipo de recomendação"
        verbose_name_plural = "Tipos de recomendação"


class TipoCriticidade(Catalogo):
    """Tipo de criticidade/condição — item 2.2.1.12."""

    cor = models.CharField("Cor (hex)", max_length=7, default="#64748b", help_text="Ex.: #ef4444")
    nivel = models.PositiveSmallIntegerField(
        "Nível", default=0, help_text="Ordem de severidade (0 = menor)."
    )

    class Meta(Catalogo.Meta):
        verbose_name = "Tipo de criticidade/condição"
        verbose_name_plural = "Tipos de criticidade/condição"
        ordering = ["nivel"]


class GrupoAcesso(Catalogo):
    """Grupos de acesso — item 2.2.1.13 (agrupamento lógico; permissões finas por perfil)."""

    class Meta(Catalogo.Meta):
        verbose_name = "Grupo de acesso"
        verbose_name_plural = "Grupos de acesso"


class Rota(BaseModel):
    """Rotas de inspeção — item 2.2.1.18."""

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="rotas")
    nome = models.CharField("Nome da rota", max_length=120)
    descricao = models.TextField("Descrição", blank=True)
    periodicidade_dias = models.PositiveIntegerField("Periodicidade (dias)", null=True, blank=True)
    equipamentos = models.ManyToManyField(Equipamento, blank=True, related_name="rotas")

    class Meta(BaseModel.Meta):
        verbose_name = "Rota de inspeção"
        verbose_name_plural = "Rotas de inspeção"

    def __str__(self):
        return f"{self.cliente} / {self.nome}"
