"""
Cadastros — Anexo I, item 2.2 e estrutura de banco item 3.1.

Hierarquia de localização (item 2.2.1.15–17):
    Cliente → Área → Setor → Equipamento → Componente
"""
import calendar
from datetime import date

from django.db import models

from apps.core.models import BaseModel


class EnderecoMixin(models.Model):
    """
    Endereço estruturado (preenchível pela busca de CEP — ViaCEP).
    Campos separados em vez de uma linha única: permite autocompletar pelo CEP,
    filtrar por cidade/UF e imprimir o endereço formatado nos laudos.
    """

    # Nunca encolher este campo: o banco em produção já tem CEPs no formato
    # "13.145-076" (10 caracteres) e o PostgreSQL recusa ALTER que trunque dados.
    cep = models.CharField("CEP", max_length=10, blank=True, help_text="Somente números ou 00000-000")
    logradouro = models.CharField("Logradouro", max_length=200, blank=True)
    numero = models.CharField("Número", max_length=20, blank=True)
    complemento = models.CharField("Complemento", max_length=100, blank=True)
    bairro = models.CharField("Bairro", max_length=100, blank=True)
    cidade = models.CharField("Cidade", max_length=100, blank=True)
    uf = models.CharField("UF", max_length=2, blank=True)
    # Mantido em sincronia com cidade/UF: já é consumido pelo Portal e pelos laudos.
    cidade_uf = models.CharField("Cidade/UF", max_length=80, blank=True, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.cidade or self.uf:
            self.cidade_uf = f"{self.cidade}/{self.uf}".strip("/")
        super().save(*args, **kwargs)

    @property
    def endereco_formatado(self) -> str:
        rua = ", ".join(p for p in [self.logradouro, self.numero] if p)
        partes = [p for p in [rua, self.complemento, self.bairro, self.cidade_uf, self.cep] if p]
        return " — ".join(partes)


class Empresa(EnderecoMixin, BaseModel):
    """Empresa CONTRATADA (prestadora) — Anexo I 3.1.1."""

    nome = models.CharField("Nome da empresa", max_length=160)
    cnpj = models.CharField("CNPJ", max_length=18, unique=True)
    contato_gestor = models.CharField("Contato gestor", max_length=120, blank=True)
    departamento = models.CharField("Departamento", max_length=120, blank=True)
    logomarca = models.ImageField("Logomarca", upload_to="logos/empresas/", null=True, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Empresa (contratada)"
        verbose_name_plural = "Empresas (contratadas)"

    def __str__(self):
        return self.nome


class Cliente(EnderecoMixin, BaseModel):
    """
    Empresa CONTRATANTE / tomador de serviço — Anexo I 3.1.3.
    Topo da hierarquia definida com o cliente:
        Cliente → Área → Setor → Equipamento → Componente → Ponto de medição.
    """

    # --- Identificação ---
    nome = models.CharField("Razão social", max_length=160)
    nome_fantasia = models.CharField("Nome fantasia", max_length=160, blank=True)
    cnpj = models.CharField("CNPJ", max_length=18, unique=True)
    unidade_negocio = models.CharField("Unidade de negócio", max_length=120, blank=True)

    # --- Contato ---
    contato_gestor = models.CharField("Contato gestor", max_length=120, blank=True)
    departamento = models.CharField("Departamento", max_length=120, blank=True)
    email = models.EmailField("E-mail", blank=True)
    telefone = models.CharField("Telefone", max_length=20, blank=True)

    logomarca = models.ImageField("Logomarca", upload_to="logos/clientes/", null=True, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Cliente (contratante)"
        verbose_name_plural = "Clientes (contratantes)"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Area(BaseModel):
    """
    Local de inspeção [Área] — item 2.2.1.15.
    No relatório aparece como "Área: 001 - SP1930 [Matriz]"
    (código - nome [complemento]).
    """

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="areas")
    codigo = models.CharField("Código", max_length=20, blank=True, help_text="Ex.: 001")
    nome = models.CharField("Área", max_length=120)
    complemento = models.CharField(
        "Complemento", max_length=120, blank=True, help_text="Ex.: Matriz, Filial"
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Área"
        verbose_name_plural = "Áreas"
        unique_together = [("cliente", "nome")]
        ordering = ["codigo", "nome"]

    def __str__(self):
        return f"{self.cliente} / {self.identificacao}"

    @property
    def identificacao(self) -> str:
        """Formato usado na Seção C do relatório: '001 - SP1930 [Matriz]'."""
        base = f"{self.codigo} - {self.nome}" if self.codigo else self.nome
        return f"{base} [{self.complemento}]" if self.complemento else base


class Setor(BaseModel):
    """
    Local de inspeção [Setor] — item 2.2.1.16.
    No relatório aparece como "Setor: Vácuo [Piso Inferior]".
    """

    area = models.ForeignKey(Area, on_delete=models.CASCADE, related_name="setores")
    codigo = models.CharField("Código", max_length=20, blank=True)
    nome = models.CharField("Setor", max_length=120)
    complemento = models.CharField(
        "Complemento", max_length=120, blank=True, help_text="Ex.: Piso Inferior"
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Setor"
        verbose_name_plural = "Setores"
        unique_together = [("area", "nome")]
        ordering = ["codigo", "nome"]

    def __str__(self):
        return f"{self.area.nome} / {self.identificacao}"

    @property
    def identificacao(self) -> str:
        """Formato usado na Seção C do relatório: 'Vácuo [Piso Inferior]'."""
        base = f"{self.codigo} - {self.nome}" if self.codigo else self.nome
        return f"{base} [{self.complemento}]" if self.complemento else base


class ClasseISO(models.TextChoices):
    """Classe da máquina p/ severidade de vibração (ISO 10816/20816)."""

    I = "I", "Classe I (≤15 kW)"
    II = "II", "Classe II (15–75 kW)"
    III = "III", "Classe III (base rígida)"
    IV = "IV", "Classe IV (base flexível)"


class CriticidadeEquip(models.TextChoices):
    """
    Criticidade do equipamento para o processo produtivo (padrão A/B/C).
    Norteia a periodicidade de monitoramento contratada (ex.: A = mensal,
    B = bimestral, C = trimestral — varia por contrato do cliente).
    """

    A = "A", "A — Alta (crítico ao processo)"
    B = "B", "B — Média (importante)"
    C = "C", "C — Baixa (auxiliar)"


class Equipamento(BaseModel):
    """
    Local de inspeção [Equipamento] / máquina — itens 2.2.1.17 e 3.1.8.

    Hierarquia completa acordada com o cliente:
        Cliente → Área → Setor → Equipamento → Sub-item → Componente

    O sub-item é um Equipamento filho (`equipamento_pai`), porque ele também é
    uma máquina: tem TAG, recebe medições e gera OSP própria. Ex.:
        CALD-EI-120-6202-01 — Caldeira EIT 12T.H2FD Nº.01   (equipamento)
          └─ Exaustor                                        (sub-item)
               ├─ Motor Elétrico                             (componente)
               └─ Mancais do Exaustor                        (componente)
    """

    setor = models.ForeignKey(Setor, on_delete=models.PROTECT, related_name="equipamentos")
    equipamento_pai = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="subitens",
        verbose_name="Equipamento principal",
        help_text="Preencha apenas se este for um sub-item (ex.: exaustor de uma caldeira).",
    )
    tag = models.CharField("TAG", max_length=60, help_text="Identificação no campo (ex.: BBA-101)")
    nome = models.CharField("Nome/Descrição", max_length=160)
    # Tipo vem do catálogo "Tipos de equipamento" (Dados de sistema). O campo texto
    # `tipo` é mantido sincronizado com o nome, para leitores antigos e relatórios.
    tipo_equipamento = models.ForeignKey(
        "TipoEquipamento", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="equipamentos", verbose_name="Tipo de equipamento",
    )
    tipo = models.CharField("Tipo (texto)", max_length=80, blank=True)
    fabricante = models.CharField("Fabricante", max_length=80, blank=True)
    modelo = models.CharField("Modelo", max_length=80, blank=True)
    numero_serie = models.CharField("Número de série", max_length=80, blank=True)
    potencia_kw = models.DecimalField("Potência (kW)", max_digits=8, decimal_places=2, null=True, blank=True)
    rotacao_nominal_rpm = models.PositiveIntegerField("Rotação nominal (RPM)", null=True, blank=True)
    classe_iso = models.CharField(
        "Classe ISO (vibração)", max_length=3, choices=ClasseISO.choices,
        default=ClasseISO.II, help_text="Define os limiares de severidade da análise de vibração.",
    )
    criticidade = models.CharField(
        "Criticidade (importância)", max_length=1, choices=CriticidadeEquip.choices,
        blank=True, help_text="Classificação A/B/C da importância no processo produtivo.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Equipamento"
        verbose_name_plural = "Equipamentos"
        unique_together = [("setor", "tag")]

    def save(self, *args, **kwargs):
        # Espelha o nome do tipo no campo texto (compatibilidade/relatórios).
        if self.tipo_equipamento_id:
            self.tipo = (self.tipo_equipamento.nome or "")[:80]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tag} — {self.nome}"

    @property
    def is_subitem(self) -> bool:
        return self.equipamento_pai_id is not None

    @property
    def nivel(self) -> int:
        """Profundidade na árvore: 0 = equipamento principal, 1 = sub-item…"""
        n, atual = 0, self.equipamento_pai
        while atual is not None and n < 10:  # trava de segurança contra ciclo
            n += 1
            atual = atual.equipamento_pai
        return n

    @property
    def caminho(self) -> str:
        """
        Localização completa, no formato que o cliente descreveu:
        '62 - Utilidades / 6202 - Geração de Vapor / CALD-… / Exaustor'.
        """
        partes = [self.nome]
        atual = self.equipamento_pai
        while atual is not None and len(partes) < 10:
            partes.append(atual.nome)
            atual = atual.equipamento_pai
        partes.reverse()
        setor = self.setor
        return " / ".join([setor.area.identificacao, setor.identificacao, *partes])

    def clean(self):
        """Impede que um equipamento vire ancestral de si mesmo."""
        from django.core.exceptions import ValidationError

        atual, visitados = self.equipamento_pai, {self.pk}
        while atual is not None:
            if atual.pk in visitados:
                raise ValidationError(
                    {"equipamento_pai": "Vínculo circular: este equipamento já está acima na hierarquia."}
                )
            visitados.add(atual.pk)
            atual = atual.equipamento_pai


class Componente(BaseModel):
    """Componente/ponto do equipamento (mancal, motor, bomba) — item 3.1.13."""

    equipamento = models.ForeignKey(Equipamento, on_delete=models.CASCADE, related_name="componentes")
    nome = models.CharField("Componente", max_length=120, help_text="Ex.: Mancal LA, Mancal LOA")

    class Meta(BaseModel.Meta):
        verbose_name = "Componente"
        verbose_name_plural = "Componentes"

    def __str__(self):
        return f"{self.equipamento.tag} / {self.nome}"


class PeriodicidadeCalibracao(models.IntegerChoices):
    """
    Frequência de calibração do instrumento — o valor é o intervalo em meses,
    o que permite calcular a data da próxima calibração.
    O relatório declara, por exemplo, 'Validade: Bienal'.
    """

    SEMESTRAL = 6, "Semestral"
    ANUAL = 12, "Anual"
    BIENAL = 24, "Bienal"
    TRIENAL = 36, "Trienal"


class Instrumento(BaseModel):
    """
    Instrumentação/coletor — itens 2.2.1.4 e 3.1.10 (com controle de calibração).
    Os dados aqui alimentam o bloco "Instrumentação Utilizada" do relatório técnico.
    """

    tipo = models.CharField("Tipo de instrumento", max_length=80)
    marca = models.CharField("Marca", max_length=80, blank=True)
    modelo = models.CharField("Modelo", max_length=80, blank=True)
    numero_serie = models.CharField("Número de série", max_length=80, blank=True)
    data_ultima_calibracao = models.DateField("Última calibração", null=True, blank=True)
    periodicidade_calibracao = models.PositiveSmallIntegerField(
        "Validade da calibração", choices=PeriodicidadeCalibracao.choices,
        default=PeriodicidadeCalibracao.BIENAL,
    )
    entidade_calibracao = models.CharField("Entidade de calibração", max_length=120, blank=True)
    software_analise = models.CharField(
        "Software de análise", max_length=120, blank=True, help_text="Ex.: OMNITREND"
    )
    # Tecnologias em que o instrumento é usado (ex.: coletor → Vibração), para
    # filtrar os instrumentos disponíveis conforme o tipo de atividade.
    # String reference: TecnologiaAnalise é definida mais abaixo neste arquivo.
    tecnologias = models.ManyToManyField(
        "cadastros.TecnologiaAnalise", blank=True, related_name="instrumentos",
        verbose_name="Tecnologias aplicáveis",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Instrumento"
        verbose_name_plural = "Instrumentos"

    def __str__(self):
        return f"{self.tipo} {self.marca} {self.modelo}".strip()

    @property
    def proxima_calibracao(self):
        """Vencimento da calibração = última calibração + validade."""
        if not self.data_ultima_calibracao:
            return None
        meses = self.periodicidade_calibracao or 24
        ano = self.data_ultima_calibracao.year + (self.data_ultima_calibracao.month - 1 + meses) // 12
        mes = (self.data_ultima_calibracao.month - 1 + meses) % 12 + 1
        dia = min(self.data_ultima_calibracao.day, calendar.monthrange(ano, mes)[1])
        return date(ano, mes, dia)

    @property
    def calibracao_vencida(self) -> bool:
        prox = self.proxima_calibracao
        return bool(prox and prox < date.today())


# =============================================================================
# Catálogos / tabelas de referência — Anexo I 2.2.1.5 a 2.2.1.14 e 2.2.1.18.
# Tabelas simples (nome + descrição) usadas para padronizar a operação e
# alimentar os selects do sistema. Mantidas parametrizáveis pelo cliente
# (sem regra "escondida" em código — alinhado à Cláusula 12.4).
# =============================================================================


class Catalogo(BaseModel):
    """Base abstrata para tabelas de referência simples."""

    nome = models.CharField("Nome", max_length=250)
    descricao = models.TextField("Descrição", blank=True)

    class Meta(BaseModel.Meta):
        abstract = True
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class TecnologiaAnalise(Catalogo):
    """Tecnologias/Tipos de análise — item 2.2.1.6."""

    sigla = models.CharField("Sigla", max_length=20, blank=True)
    # Imagem/ícone que identifica a tecnologia (aparece na capa do relatório).
    imagem = models.ImageField("Imagem/ícone", upload_to="tecnologias/", null=True, blank=True)

    class Meta(Catalogo.Meta):
        verbose_name = "Tecnologia/Tipo de análise"
        verbose_name_plural = "Tecnologias/Tipos de análise"


class Norma(Catalogo):
    """Normas técnicas (NBR/ISO/IEEE) — item 2.2.1.5."""

    codigo = models.CharField("Código", max_length=40, help_text="Ex.: NBR 10816, ISO 20816")
    orgao = models.CharField("Órgão", max_length=40, blank=True, help_text="ABNT, ISO, IEEE…")
    # Vínculo com as tecnologias de análise às quais a norma se aplica
    # (ex.: NBR 10816 → Vibração). Muitas-para-muitas, opcional.
    tecnologias = models.ManyToManyField(
        TecnologiaAnalise, blank=True, related_name="normas",
        verbose_name="Tecnologias aplicáveis",
    )

    class Meta(Catalogo.Meta):
        verbose_name = "Norma"
        verbose_name_plural = "Normas (NBRs)"

    def __str__(self):
        return f"{self.codigo} — {self.nome}" if self.codigo else self.nome


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

    tecnologias = models.ManyToManyField(
        TecnologiaAnalise, blank=True, related_name="tipos_componente",
        verbose_name="Tecnologias aplicáveis",
    )

    class Meta(Catalogo.Meta):
        verbose_name = "Tipo de componente"
        verbose_name_plural = "Tipos de componente"


class TipoAnomalia(Catalogo):
    """Tipo de anomalia — item 2.2.1.10."""

    tecnologias = models.ManyToManyField(
        TecnologiaAnalise, blank=True, related_name="tipos_anomalia",
        verbose_name="Tecnologias aplicáveis",
    )

    class Meta(Catalogo.Meta):
        verbose_name = "Tipo de anomalia"
        verbose_name_plural = "Tipos de anomalia"


class TipoRecomendacao(Catalogo):
    """Tipo de recomendação — item 2.2.1.11."""

    tecnologias = models.ManyToManyField(
        TecnologiaAnalise, blank=True, related_name="tipos_recomendacao",
        verbose_name="Tecnologias aplicáveis",
    )

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


class Condicao(Catalogo):
    """
    Condição do equipamento no momento da inspeção — alimenta o campo "Condição"
    da folha de campo. Cada condição tem uma sigla/tag (ex.: OK, PDP, PDM, IC),
    a nomenclatura (`nome`) e um descritivo (`descricao`).

    Ex.: "OK/Normal", "Parado devido ao processo (PDP)", "Parado devido à manutenção
    (PDM)" (não geram ação) ou condições que exigem registrar uma análise
    (`gera_acao=True` → o formulário de campo abre o botão de análise). Não é
    vinculada a tecnologia (são poucas; aparecem para todas).
    """

    sigla = models.CharField("Sigla", max_length=20, blank=True, help_text="Ex.: OK, PDP, PDM, IC, GR0…")
    gera_acao = models.BooleanField(
        "Gera análise", default=False,
        help_text="Se marcado, selecionar esta condição exige registrar uma análise no campo.",
    )
    cor = models.CharField("Cor (hex)", max_length=7, default="#64748b", help_text="Ex.: #22c55e")
    nivel = models.PositiveSmallIntegerField(
        "Nível", default=0, help_text="Ordem de severidade (0 = menor)."
    )

    class Meta(Catalogo.Meta):
        verbose_name = "Condição do equipamento"
        verbose_name_plural = "Condições do equipamento"
        ordering = ["nivel", "nome"]


class GrupoAcesso(Catalogo):
    """Grupos de acesso — item 2.2.1.13 (agrupamento lógico; permissões finas por perfil)."""

    class Meta(Catalogo.Meta):
        verbose_name = "Grupo de acesso"
        verbose_name_plural = "Grupos de acesso"


class Rota(BaseModel):
    """Rotas de inspeção — item 2.2.1.18."""

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="rotas")
    nome = models.CharField("Nome da rota", max_length=120)
    # Tecnologia da rota (ex.: Vibração, Termografia) — uma rota é por técnica.
    tecnologia = models.ForeignKey(
        TecnologiaAnalise, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="rotas", verbose_name="Tecnologia",
    )
    descricao = models.TextField("Descrição", blank=True)
    periodicidade_dias = models.PositiveIntegerField("Periodicidade (dias)", null=True, blank=True)
    # Equipamentos que compõem a rota (montados pela árvore Área → Setor → Equipamento).
    equipamentos = models.ManyToManyField(Equipamento, blank=True, related_name="rotas")

    class Meta(BaseModel.Meta):
        verbose_name = "Rota de inspeção"
        verbose_name_plural = "Rotas de inspeção"

    def __str__(self):
        return f"{self.cliente} / {self.nome}"
