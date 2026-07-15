# Fase 1 — Discovery: Regras de Negócio dos Módulos Técnicos (Anexo I 2.3.2)

> Entregável da **Fase 1** descrita no prompt do cliente. Detalha as regras de negócio
> ANTES da modelagem definitiva do banco. Este documento serve de base para os
> `models.py` da app `coletas`. As faixas/limiares aqui são **valores de referência de
> engenharia** e devem ser **confirmados com a ThermoProActive** (ver §6 de cada módulo).

O item 2.3.2 do Anexo I tem **10 categorias** de coleta técnica. Abaixo o detalhamento
completo do módulo **2.3.2.1 — Análise de Vibração** (implementado nesta fundação) e o
resumo + perguntas abertas das demais 9 (a serem detalhadas no mesmo formato).

---

## 2.3.2.1 — Análise de Vibração

Subtipos do Anexo I:
- **2.3.2.1.1** Sistemas Mecânicos Dinâmicos (máquinas rotativas: motores, bombas, ventiladores)
- **2.3.2.1.2** ODS — *Operational Deflection Shape* (forma de deflexão operacional)
- **2.3.2.1.3** Sistemas Mecânicos Estáticos (estruturas, tubulações, bases)

### 1. Campos coletados por tipo de medição

**Comuns a toda coleta de vibração**
| Campo | Tipo | Observação |
|-------|------|------------|
| equipamento | FK | máquina inspecionada |
| componente | FK | mancal/ponto (LA/LOA, motor/bomba) |
| ponto_medicao | texto | identificação do ponto (ex.: "Mancal LA") |
| direcao | enum | Horizontal / Vertical / Axial (H/V/A) |
| data_hora | datetime | item 2.3.1.8 |
| rotacao_rpm | decimal | rotação no instante da coleta |
| instrumento | FK | item 2.2.1.4 / 3.1.10 (com calibração) |
| temperatura_ponto | decimal °C | opcional |
| condicao_operacional | enum | Carga nominal / Parcial / Vazio |

**Sistemas Mecânicos Dinâmicos (2.3.2.1.1)**
| Grandeza | Unidade | Uso |
|----------|---------|-----|
| Velocidade RMS global (Vrms) | mm/s | severidade global (ISO 10816/20816) |
| Aceleração RMS | g ou m/s² | defeitos de alta frequência (rolamento) |
| Aceleração de pico / Envelope (gE) | gE | rolamento/engrenamento (demodulação) |
| Deslocamento pico-a-pico | µm | baixa rotação / folga |
| Fator de crista | adimensional | impactos (>5 indica defeito incipiente) |
| Espectro FFT (frequência × amplitude) | Hz × mm/s | diagnóstico de causa (1×, 2×, BPFO, BPFI…) |

**ODS (2.3.2.1.2)** — amplitude e **fase** por ponto/direção da estrutura para reconstruir o
modo de deflexão. Campos extra: `fase_graus`, `frequencia_analisada_hz`, malha de pontos.

**Sistemas Mecânicos Estáticos (2.3.2.1.3)** — foco em deslocamento (µm/mm) e frequência
natural/ressonância; comparação com limites estruturais, não ISO 10816.

### 2. Unidades e faixas típicas (referência ISO 10816/20816)

Severidade por **velocidade RMS (mm/s)**, dependente da classe da máquina:

| Zona ISO | Classe I (≤15kW) | Classe II (15–75kW) | Classe III rígida | Classe IV flexível | Significado |
|----------|------------------|---------------------|-------------------|--------------------|-------------|
| **A** (nova) | ≤ 0,71 | ≤ 1,12 | ≤ 1,8 | ≤ 2,8 | Boa |
| **B** (aceitável) | ≤ 1,8 | ≤ 2,8 | ≤ 4,5 | ≤ 7,1 | Operação contínua OK |
| **C** (tolerável) | ≤ 4,5 | ≤ 7,1 | ≤ 11,2 | ≤ 18,0 | Restrito / monitorar |
| **D** (inadmissível) | > 4,5 | > 7,1 | > 11,2 | > 18,0 | Risco de dano |

→ Os limiares por classe ficam **parametrizáveis em tabela** (`FaixaSeveridade`), não hard-coded,
para o cliente ajustar sem alterar código (alinhado à Cláusula 12.4).

### 3. Regras de classificação de anomalia / criticidade

```
Severidade global (zona ISO) → criticidade base:
  Zona A → NORMAL          Zona C → ALERTA
  Zona B → NORMAL          Zona D → CRÍTICO

Escalonamento por evolução (item 2.4.1.2 / 2.4.1.3):
  Se Vrms atual > 1,5 × média das 3 últimas coletas → eleva 1 nível de criticidade.
  Se Vrms cruza limite de zona em < 30 dias               → tendência ACELERADA → ALERTA mínimo.

Assinaturas espectrais (diagnóstico assistido — item 2.4.2.3):
  pico dominante em 1×RPM            → desbalanceamento
  pico em 2×RPM + axial alto         → desalinhamento
  bandas laterais em BPFO/BPFI       → defeito de rolamento (pista ext./int.)
  fator de crista > 5 / gE elevado   → defeito incipiente de rolamento
```
Resultado: cada coleta recebe `criticidade` (NORMAL/ALERTA/CRÍTICO) + `diagnostico_sugerido`.
Coleta CRÍTICA dispara (fase futura) **OSP automática** (item 2.6.1.1).

### 4. Perfis que registram / visualizam (Anexo I 2.1.2)
| Perfil | Registra coleta | Vê dados técnicos | Vê laudo final |
|--------|:---:|:---:|:---:|
| Administrador | ✅ | ✅ | ✅ |
| Gestor/Supervisor | ✅ | ✅ | ✅ |
| Técnico/Analista | ✅ | ✅ | ✅ |
| Cliente [gestor corporativo] | ❌ | 🟡 resumo | ✅ |
| Cliente [gestor local] | ❌ | 🟡 resumo | ✅ (sua unidade) |
| Cliente [PCM] | ❌ | ✅ (sua planta) | ✅ |
| Cliente [manutentores] | ❌ | 🟡 OSP vinculada | 🟡 |

### 5. Perguntas a fazer à ThermoProActive (lacunas a fechar)
1. Quais **normas** vocês adotam como padrão (ISO 10816/20816, NBR específica)? Limiares por classe são os da ISO ou possuem tabela própria?
2. A classe da máquina (I–IV / rígida-flexível) é cadastrada por equipamento ou definida na coleta?
3. Vocês importam dados do **coletor** (ex.: CSV/arquivo do equipamento) ou digitam manualmente? Qual formato/coletor (modelo)?
4. Guardam o **espectro FFT completo** (vetor de pontos) ou apenas as grandezas globais + picos relevantes?
5. Para ODS: qual a malha de pontos e como nomeiam os pontos da estrutura?
6. A evolução/tendência considera janela fixa (últimas N coletas) ou período (ex.: 90 dias)?
7. Quem assina o laudo de vibração (conselho de classe — campo 3.1.2.12)?

---

## Resumo das outras 9 categorias (a detalhar no mesmo formato)

| Item | Categoria | Grandezas-chave | Norma/Referência típica |
|------|-----------|-----------------|--------------------------|
| 2.3.2.2 | Termografia IV (elétrico, mecânico, processos) | ΔT (°C) ponto×referência, emissividade, corrente/carga | NBR 15572, NETA — ΔT: 1–3°C investigar, 4–15°C reparo programado, >15°C imediato |
| 2.3.2.3 | Análise de Fluidos (lubrificantes/isolantes) | FQ (viscosidade, TAN/TBN, água), CR (espectrometria Fe/Cu/Si ppm), contagem de partículas ISO 4406, PCB, 2-FAL | ISO 4406, ASTM D, NBR (óleo isolante) |
| 2.3.2.4 | Ensaios Elétricos — Transformadores | RxT/TTR (relação de transformação %erro), RxI (MΩ/GΩ, índice polarização), RxO (resistência ôhmica) | NBR 5356, IEEE C57 |
| 2.3.2.5 | Ensaios Elétricos — Motores | RxI (resistência de isolação MΩ, IP/IA), index | IEEE 43 (PI ≥ 2,0 bom) |
| 2.3.2.6 | Ultrassom (elétrico/mecânico) | nível dB, frequência, tipo (corona/tracking/vazamento/atrito) | — |
| 2.3.2.7 | Medição de espessura | espessura (mm), perda %, taxa de corrosão | ultrassom de espessura |
| 2.3.2.8 | Manutenção corretiva (alinhamento laser eixos/polias, balanceamento) | desalinhamento angular/paralelo (mm/100mm), tolerância residual (g·mm) | normas do fabricante |
| 2.3.2.9 | Sensitiva (inspeção sensorial) | checklist qualitativo (ruído, folga, vazamento, odor) | subjetivo + foto |
| 2.3.2.10 | Qualidade de Energia | THD%, desequilíbrio de tensão %, fator de potência, harmônicos | IEEE 519, PRODIST Módulo 8 |

> Para cada uma, repetir o prompt da Fase 1 com os 5 pontos (campos, unidades/faixas,
> regras de anomalia, perfis, perguntas ao cliente). A modelagem da app `coletas` usa
> herança de uma `Coleta` base + tabela específica por tipo de medição, de modo que cada
> nova categoria entra sem refatorar as anteriores.
