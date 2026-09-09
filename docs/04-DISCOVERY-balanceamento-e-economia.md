# Fase 2 — Discovery: Balanceamento Dinâmico em Campo e Economia Energética

> Entregável de discovery sobre as duas planilhas de campo do Fabrício:
> `Planilha Balanceamentos.xlsx` e `Economia Geradas com Alinhamentos e Balanceamentos.xlsx`.
> Decodifica o que cada célula faz, aponta as inconsistências encontradas e propõe a
> modelagem no sistema. Segue o formato do `01-DISCOVERY-modulos-tecnicos.md`:
> nada é implementado antes de §7 (perguntas abertas) ser confirmado com a ThermoProActive.
>
> Enquadramento no Anexo I: **2.3.2.8 — Manutenção Corretiva** (alinhamento a laser e
> balanceamento em campo). Hoje o sistema trata isso como `TipoAnalise.CORRETIVA`
> dentro da `MedicaoTecnica` genérica (`grandeza/valor/unidade`) — e §5 mostra por que
> essa estrutura **não comporta** os dados das planilhas.

---

## 1. `Planilha Balanceamentos.xlsx` — o que ela é

Workbook com **4 abas**, na verdade **duas variantes do mesmo relatório**:

| Aba | Papel |
|-----|-------|
| `Bal-1P` | Folha de balanceamento em **1 plano** (dados + resultado) |
| `Graf-O 1P` | Aba auxiliar: converte fases em coordenadas para o gráfico polar de 1P |
| `Bal-2P` | Folha de balanceamento em **2 planos** |
| `Graf-O 2P` | Aba auxiliar do gráfico polar de 2P |

As abas `Graf-O` **não têm dado de campo** — são 100% derivadas (seno/cosseno das fases).
No sistema elas simplesmente deixam de existir: viram cálculo na renderização do gráfico.

### 1.1 Cabeçalho (idêntico nas duas)

| Célula | Conteúdo do exemplo | Significado |
|--------|--------------------|-------------|
| `C1` | `Ventilador Espargidor` | Equipamento |
| `J1` | `29,74 Hz` | Rotação de balanceamento (≙ 1.784 RPM) |
| `C2`/`D2` | `Plano 1` / `0° / 30,0 g` | Massa de teste (*trial mass*) do plano 1 |
| `E2`/`F2` | `Plano 2` / `0° / 30,0 g` | Massa de teste do plano 2 (só em `Bal-2P`) |

> `Bal-2P!C2` está grafado **"Palno 1"** (typo na origem).

### 1.2 Corpo — as três corridas (*runs*)

Uma linha por **ponto de medição** (mancal + direção), três pares de colunas:

| Bloco | Colunas | Campos |
|-------|---------|--------|
| `REFERENCE RUN (ANTES)` | C, D | amplitude `mm/s` + fase `°` |
| `TRIAL RUN` | E, F | amplitude `mm/s` + fase `°` (com a massa de teste) |
| `TRIM RUN` | G, H | amplitude `mm/s` + fase `°` (resultado final) |

Dados do exemplo:

| Aba | Mancal | Dir. | Ref. | Trial | Trim | Redução |
|-----|--------|------|------|-------|------|---------|
| `Bal-1P` | 2 | H | 12,31 mm/s @ 110° | 23,95 @ 133° | **1,70 @ 136°** | **86,2 %** |
| `Bal-2P` | 3 | H | 20,00 mm/s @ 210° | 50,00 @ 235° | **0,90 @ 240°** | **95,5 %** |
| `Bal-2P` | 4 | H | 12,31 mm/s @ 60° | 23,95 @ 80° | **1,70 @ 75°** | **86,2 %** |

E a linha **`Massas`** (última linha), que reusa as mesmas colunas com **outro significado**:
em vez de (mm/s, fase) ela guarda **(massa em g, ângulo em °)** de cada corrida —
`Bal-1P`: 0 g (ref) → 30 g (trial) → **100 g** (trim). `Bal-2P`: 0 g/0° → 30 g/40° → 100 g/110°.

### 1.3 Bloco `CURVA REDUÇÃO (x100%)` — colunas I/J

```
J6 = G6 * I6 / C6      →  vibração residual = trim ÷ reference   (I6 = 1 = base 100 %)
J7 = I6 - J6           →  ganho             = 1 − residual        (= redução obtida)
```

`Bal-1P`: 1,70 / 12,31 = 0,138 → **13,8 % residual / 86,2 % de redução**.

### 1.4 As colunas L:P (1P) e L:T (2P) — só rótulos de gráfico

São a "área de serviço" que alimenta os gráficos: pares `Antes/Depois` em mm/s e em %,
mais os textos de anotação (`"136°"`, `"100 g"`). Nada de dado novo. No sistema, some.

### 1.5 Os 4 gráficos embutidos

| Gráfico | Tipo real | O que mostra |
|---------|-----------|--------------|
| `chart1` / `chart3` | *doughnut* + *scatter* | **Mostrador polar**: rosca de 12 fatias iguais (marcação de 30°) + 3 vetores (reference / trial / trim) |
| `chart2` / `chart4` | *line* | **Antes × Depois** em mm/s e em % |

O vetor polar é montado nas abas `Graf-O`:

```
ângulo = (fase / 360) * 2π          x2 = COS(ângulo)     y2 = SIN(ângulo)
```

> **Observação técnica:** o raio do vetor é sempre **1** (vetor unitário). O mostrador
> mostra só a **direção da fase**, não a amplitude. Ao reimplementar, dá para escalar o
> raio pela amplitude (mm/s) e ganhar um polar de verdade — a convergência
> reference → trial → trim fica visível num gráfico só. **Decisão do Fabrício** (§7).

---

## 2. `Economia Geradas com Alinhamentos e Balanceamentos.xlsx`

Aba única, 13 linhas. Calcula a economia elétrica gerada pelo serviço (vale para
**alinhamento E balanceamento** — daí o nome do arquivo).

### 2.1 Entradas

| Célula | Campo | Exemplo |
|--------|-------|---------|
| `B1` | Tensão do motor | 380 V |
| `B2` | Corrente elétrica **antes** | 71,0 A |
| `B3` | Corrente elétrica **após** | 66,2 A |
| `B4` | Fator de potência | 0,93 |
| `B5` | Constante √3 | 1,732 |
| `B6` | Regime diário de operação | 20 h |
| `B7` | Custo da energia | R$ 0,35 |
| `B13` | Custo do serviço | R$ 1.606,00 |

### 2.2 Fórmulas

```
B9  = (B1 * (B2 - B3) * B4 * B5) / 1000     → 2,938  (redução de demanda, kW)
B11 = B9 * B6 * 365 * B7                    → R$ 7.506,66 / ano
C11 = B11 / B13                             → 4,674
```

Confere: 380 × 4,8 × 0,93 × 1,732 / 1000 = **2,938 kW**;
2,938 × 20 h × 365 d = 21.448 kWh/ano × R$ 0,35 = **R$ 7.506,66/ano**.

### 2.3 Correções necessárias antes de virar cliente-facing

1. **Unidades erradas nos rótulos.** `C9` diz `KW/h` mas `B9` é **kW** (redução de
   demanda). `C7` diz `KW/h` mas `B7` é **R$/kWh**. A grafia correta é `kW`, `kWh`,
   `R$/kWh`. Num relatório assinado isso é revisado pelo cliente.
2. **`C11` não é payback.** 4,674 é *quantas vezes o serviço se paga em um ano*.
   O payback é o inverso: 1.606 ÷ 7.506,66 = **0,214 ano ≈ 2,6 meses ≈ 78 dias**.
   O rótulo `A11` ("PayBack | Ano") mistura as duas coisas. Proponho exibir os dois,
   nomeados: **Economia anual (R$)**, **Payback (meses)** e **Retorno (×/ano)**.
3. **A economia anual em kWh não aparece** (21.448 kWh/ano) — é o número que o cliente
   leva para a meta de eficiência energética dele. Vale expor.
4. **Premissas implícitas** que precisam ir impressas junto do resultado: carga trifásica
   equilibrada, tensão e fator de potência inalterados entre o antes e o depois, e a
   corrente medida no mesmo ponto de operação. Sem isso o número não se sustenta numa
   auditoria.
5. `B5 = 1,732` é constante literal; no sistema vira `√3` calculado.
6. `365` está *hardcoded* na fórmula — deve ser um campo (dias/ano de operação), porque
   planta que para em julho não opera 365 dias.

---

## 3. Inconsistências encontradas nas planilhas (para confirmar, não para "consertar" sozinho)

| # | Onde | O quê |
|---|------|-------|
| 1 | `Bal-1P!N5` | `=H7` (massa de trim, 100 g) usada como se fosse **percentual**. Só "funciona" porque a massa vale 100 e o percentual base também. Em `Bal-2P` está certo (`=I6*100`). **É bug de planilha** — some na migração. |
| 2 | `Bal-2P` | O bloco de anotação trata **mancal 3 = Plano 1** e **mancal 4 = Plano 2**. Isso confunde *ponto de medição* com *plano de correção* — coisas diferentes (um plano pode ser avaliado por dois mancais). No modelo proposto elas ficam separadas. |
| 3 | Linha `Massas` | Reusa as colunas de (mm/s, fase) para guardar (g, °). Legível para quem fez, ilegível para o sistema. Vira tabela própria. |
| 4 | `Bal-2P!C2` | `"Palno 1"` — typo. |
| 5 | Todas | **Não há critério de aceitação.** A planilha diz que reduziu 86 %, mas não diz se o resultado final está dentro da norma. O sistema já tem `rules.classificar_vibracao()` + `Equipamento.classe_iso` — o trim de 1,70 mm/s pode ser classificado automaticamente em zona ISO 10816/20816 e o serviço ganha um **veredito**, não só um percentual. Ver §6.3. |
| 6 | Todas | Sem data, sem analista, sem instrumento, sem nº de OSP. Rastreabilidade zero — o contrato (item 3.1.10) exige instrumento com calibração vigente. |

---

## 4. Como isso se encaixa no fluxo que já existe

O balanceamento **não é uma coleta de rota** — é uma **intervenção**. O ciclo real é:

```
Rota de vibração  →  Achado "desbalanceamento"  →  OSP  →  SERVIÇO DE BALANCEAMENTO  →  economia
   (já existe)          (já existe)            (já existe)      (não existe)         (não existe)
```

Ou seja: as duas planilhas são o **fechamento do ciclo preditivo** que o sistema hoje
interrompe na OSP. É por isso que elas merecem modelo próprio e não um `MedicaoTecnica`.

O `seed_relatorio.py` já cadastra a recomendação *"Desbalanceamento → Balancear o rotor
em campo"* — o serviço proposto é exatamente o que executa essa recomendação.

---

## 5. Por que `MedicaoTecnica` não serve

`MedicaoTecnica` é `(grandeza, valor, unidade, valor_referencia, parametros JSON)` — um
número por linha. Um balanceamento de 2 planos tem:

- 3 corridas × 2 grandezas (amplitude + fase) × N pontos = 12+ números **correlacionados**;
- massas de correção por plano por corrida;
- derivados que precisam ser consultáveis (redução %, residual %);
- dois gráficos que dependem da **relação** entre esses números.

Enfiar isso em `parametros JSON` mata consulta, histórico e o gráfico. O próprio
docstring de `apps/coletas/models.py` já prevê a saída certa:

> *"cada novo tipo de análise do item 2.3.2 vira uma nova tabela vinculada a `Inspecao`,
> sem alterar esta."*

É o mesmo caminho de `MedicaoVibracao` e `MedicaoTermografia`.

---

## 6. Proposta de modelagem

> **Estado da implementação (08/09/2026)**
> · **Fase 1 — CONCLUÍDA:** `rules.py` — motor de cálculo puro, sem banco.
> · **Fase 2 — CONCLUÍDA:** `models.py` + migration `0001_initial` + `admin.py`.
> · **Fase 3 — CONCLUÍDA:** `serializers.py`, `views.py`, `urls.py` — API em `/api/servicos/`.
> · **22 testes passando** (`manage.py test apps.servicos`), com os números das duas
>   planilhas como critério de aceitação: se um teste quebrar, o sistema deixou de bater
>   com a planilha do Fabrício.
> · **Fase 4 — CONCLUÍDA:** `/servicos`, `/servicos/novo` e `/servicos/[id]` (folha de campo).
> · **Fase 5 — CONCLUÍDA:** `components/balanceamento-graficos.tsx` — mostrador polar e
>   antes×depois em SVG inline, paleta validada para daltonismo nos temas claro e escuro
>   (tokens `--viz-reference/trial/trim` em `globals.css`).
> · Fase 6 (seção do relatório técnico): pendente.


### 6.1 Nova app `servicos` (ou `apps/corretiva`)

Escopo: serviços de intervenção em campo — balanceamento **e** alinhamento (a planilha de
economia serve aos dois). Quatro modelos:

```python
class TipoServico(models.TextChoices):
    BALANCEAMENTO = "BALANCEAMENTO", "Balanceamento dinâmico em campo"
    ALINHAMENTO   = "ALINHAMENTO",   "Alinhamento a laser"


class ServicoCampo(BaseModel):
    """Cabeçalho da intervenção. Fecha o ciclo Achado → OSP → execução."""
    cliente        = FK(Cliente)
    equipamento    = FK(Equipamento)
    tipo           = CharField(choices=TipoServico)
    osp            = FK(OSP, null=True)          # origem (opcional)
    achado         = FK(Achado, null=True)       # análise que originou (opcional)
    relatorio      = FK(Relatorio, null=True)    # em que laudo sai
    analista       = FK(User)
    instrumento    = FK(Instrumento, null=True)  # rastreabilidade (item 3.1.10)
    data_execucao  = DateField()
    rotacao_hz     = Decimal(5,2, null=True)     # "29,74 Hz"
    rotacao_rpm    = PositiveInteger(null=True)  # derivada: hz × 60
    observacoes    = TextField(blank=True)
    custo_servico  = Decimal(12,2, null=True)    # entra no payback


class BalanceamentoPlano(BaseModel):
    """Plano de correção (1 ou 2). Onde a massa é fixada."""
    servico         = FK(ServicoCampo, related_name="planos")
    numero          = PositiveSmallInteger()         # 1 ou 2
    descricao       = CharField(blank=True)          # "lado acoplamento"
    massa_teste_g   = Decimal(8,2, null=True)        # trial mass  — "30,0 g"
    angulo_teste    = Decimal(5,1, null=True)        #             — "0°"
    massa_final_g   = Decimal(8,2, null=True)        # massa que ficou — "100 g"
    angulo_final    = Decimal(5,1, null=True)        #                 — "110°"


class BalanceamentoPonto(BaseModel):
    """Um ponto de medição (mancal + direção) × as três corridas."""
    servico        = FK(ServicoCampo, related_name="pontos")
    numero_mancal  = PositiveSmallInteger()
    direcao        = CharField(choices=Direcao)      # reusa H/V/A de coletas
    reference_mms  = Decimal(7,2);  reference_fase = Decimal(5,1)
    trial_mms      = Decimal(7,2, null=True); trial_fase = Decimal(5,1, null=True)
    trim_mms       = Decimal(7,2);  trim_fase      = Decimal(5,1)
    # calculados em save(), editable=False — padrão MedicaoVibracao
    residual_pct   = Decimal(6,3, editable=False)    # trim / reference
    reducao_pct    = Decimal(6,3, editable=False)    # 1 − residual
    zona_iso       = CharField(1, editable=False)    # ← rules.classificar_vibracao(trim)
    criticidade    = CharField(editable=False)


class EconomiaEnergetica(BaseModel):
    """Planilha de economia. OneToOne com o serviço (vale p/ alinhamento e balanceamento)."""
    servico          = OneToOne(ServicoCampo, related_name="economia")
    tensao_v         = Decimal(8,2)
    corrente_antes_a = Decimal(9,2)
    corrente_apos_a  = Decimal(9,2)
    fator_potencia   = Decimal(4,3)    # sem default — medido no motor
    horas_dia        = Decimal(4,1)    # sem default — regime real daquele equipamento
    dias_ano         = PositiveSmallInteger()   # era hardcoded em 365 na planilha
    custo_kwh        = Decimal(8,4)    # R$/kWh — tarifa vigente informada na hora
    # calculados, editable=False
    reducao_kw       = Decimal(10,4)   # V·ΔI·FP·√3 / 1000
    economia_kwh_ano = Decimal(12,2)   # reducao_kw × horas_dia × dias_ano
    economia_rs_ano  = Decimal(12,2)   # × custo_kwh
    payback_meses    = Decimal(6,2)    # custo_servico / economia_rs_ano × 12
    retorno_ano      = Decimal(8,3)    # economia_rs_ano / custo_servico  (o "4,674")
```

**Sobre valores padrão:** não existem. Decisão do Fabrício (08/09/2026) — tensão,
correntes, fator de potência, regime de operação, custo do kWh e custo do serviço são
**todos coletados na hora**, medidos naquele equipamento naquele dia. Nenhum campo tem
`default=`, nada é herdado do cadastro do cliente e `rules.calcular_economia()` exige
todos os argumentos: faltando um, levanta erro em vez de assumir. Um default silencioso
(FP 0,93, 365 dias/ano, custo zero) produziria um número plausível que ninguém mediu —
o tipo de erro que passa na revisão e chega ao relatório assinado.

**Sobre 1 plano × 2 planos:** não são dois modelos — é `servico.planos.count()`. As duas
abas da planilha viram um formulário só, que mostra o segundo plano quando marcado.

### 6.2 Regras de cálculo — `apps/servicos/rules.py`

Espelha `coletas/rules.py` e `rules_tecnicas.py`: função pura, testável, com os limiares
declarados no topo do arquivo (Cláusula 12.4 — nada de regra escondida).

```python
def calcular_balanceamento(reference_mms, trim_mms) -> ResultadoBalanceamento
def calcular_economia(tensao, i_antes, i_apos, fp, horas, dias, custo_kwh, custo_servico)
```

`√3` calculado (`Decimal(3).sqrt()`), não a constante 1,732.

### 6.3 Veredito automático (o que a planilha não faz)

No `save()` de `BalanceamentoPonto`, reusar o motor que já existe:

```python
resultado = rules.classificar_vibracao(
    classe_iso=self.servico.equipamento.classe_iso,
    velocidade_rms=self.trim_mms,
)
```

O relatório passa a dizer *"final 1,70 mm/s — Zona A (ISO 10816, classe II) — aprovado"*
em vez de só *"redução de 86,2 %"*. É a diferença entre um número e um laudo.

### 6.4 API (DRF, padrão das apps existentes)

```
GET/POST  /api/servicos/                    lista + criação do cabeçalho
GET/PATCH /api/servicos/{id}/               detalhe (planos + pontos + economia aninhados)
POST      /api/servicos/{id}/planos/
POST      /api/servicos/{id}/pontos/
PUT       /api/servicos/{id}/economia/
GET       /api/servicos/{id}/relatorio/     payload pronto do laudo (padrão montar_relatorio_tecnico)
```

### 6.5 Frontend

- **`/servicos`** e **`/servicos/[id]`** — nova entrada de menu (irmã de `/inspecoes`),
  porque é intervenção, não coleta de rota.
- Formulário em 3 blocos, na ordem em que o técnico trabalha no campo:
  **Reference → Trial → Trim**, com a redução calculada ao vivo a cada linha.
- **Gráficos em SVG inline**, sem biblioteca proprietária (Cláusula 12.4), do mesmo jeito
  que o relatório já é impresso a partir de HTML:
  - **mostrador polar** — círculo com marcação de 30°, três vetores (reference / trial /
    trim) e as anotações de fase e massa;
  - **antes × depois** — barras com o Δ e o percentual em destaque.
- **Card de economia** com as entradas editáveis e os quatro resultados
  (kW, kWh/ano, R$/ano, payback) recalculando na digitação, e as premissas impressas.

### 6.6 Relatório

Nova seção no laudo técnico (`laudos/relatorio.py` + template de impressão), no mesmo
layout plano do PDF de referência do Fabrício: cabeçalho do equipamento → tabela das três
corridas → mostrador polar + antes/depois lado a lado → massas aplicadas por plano →
veredito ISO → quadro de economia e payback.

---

## 7. Perguntas abertas — confirmar com o Fabrício antes de implementar

1. **Payback:** confirmar que `C11` (4,674) é "retorno ×/ano" e que o payback em meses
   (2,6) é o número que ele quer no relatório do cliente — ou os dois?
2. **Mostrador polar:** manter vetor unitário (só fase, como hoje) ou escalar o raio pela
   amplitude para mostrar a convergência?
3. **Planos × mancais:** em `Bal-2P`, mancal 3 e mancal 4 são mesmo os planos 1 e 2, ou foi
   simplificação daquele caso específico? Existe caso com 2 planos e 3+ pontos medidos?
4. **Direção:** as planilhas só usam H. Registra V e A também, ou H sempre basta?
5. **Norma de aceitação:** balanceamento residual pela **ISO 21940-11** (grau G, ex.: G2.5)
   ou basta o veredito de vibração pela ISO 10816/20816 já implementada?
6. ~~**Custo do serviço (R$ 1.606):** é por equipamento, por OS, por tabela de preço?~~
   **RESPONDIDO (08/09/2026):** digitado a cada serviço. Sem tabela de preço, sem default.
7. ~~**Custo do kWh e horas/dia:** por cliente (cadastro) ou digitados a cada serviço?~~
   **RESPONDIDO (08/09/2026):** digitados a cada serviço. A sugestão de puxar do cadastro
   do cliente foi recusada — nada vem pré-preenchido.
8. **Alinhamento:** a planilha de economia serve aos dois. Qual é a folha de campo do
   **alinhamento a laser** (desalinhamento angular/paralelo, mm/100mm)? Ela existe em
   outro arquivo? Modelar os dois juntos sai mais barato do que voltar depois.
9. ~~**Fator de potência 0,93:** fixo, ou medido por motor?~~
   **RESPONDIDO (08/09/2026):** medido, por motor. O 0,93 da planilha era daquele caso.
10. **Corrente antes/depois:** medida com que instrumento, e ele entra na rastreabilidade
    de calibração como os demais?
