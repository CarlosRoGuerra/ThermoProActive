"""
Conteúdo da Carta ao Cliente dos relatórios de transformador (óleo isolante e
ensaios elétricos).

Os relatórios de referência (2025-12_TRF-001) não trazem carta: estes textos são a
PROPOSTA de 24/09/2026, escrita a partir das normas e guias citados nas fichas
(IEEE C57.104, NBR 5356, ANSI/NETA ATS) — validar com o cliente (docs/10 §7.7).
"""

CONTEUDO_OLEO = (
    "Seção A – Carta ao Cliente",
    "Seção B – KPI’s Dashboard",
    "Seção C – Relação de Equipamentos Contemplados",
    "Seção D – Fichas da Análise do Óleo Isolante [coleta e resultados dos ensaios]",
)

CONTEUDO_ELETRICO = (
    "Seção A – Carta ao Cliente",
    "Seção B – KPI’s Dashboard",
    "Seção C – Relação de Equipamentos Contemplados",
    "Seção D – Fichas dos Ensaios Elétricos [registro e resultados dos ensaios]",
)

_CRITICIDADE = ("Criticidade", "Prioridade do laudo de cada ensaio: Rotina, Alerta ou Crítica. Não se confunde com o Grau de Risco das inspeções.")

GLOSSARIO_OLEO = (
    ("6.1", "Ensaios", ""),
    ("6.1.1", "FQ", "Físico-Químico: ensaios das propriedades físicas e químicas do óleo isolante — viscosidade, densidade, fator de potência, índice de neutralização, teor de água, rigidez dielétrica, tensão interfacial, cor e aparência."),
    ("6.1.2", "CR", "Cromatográfico: análise dos gases dissolvidos no óleo isolante, que indicam falhas térmicas ou elétricas em desenvolvimento."),
    ("6.1.3", "PCB", "Teor de bifenilas policloradas no óleo isolante, em mg/kg."),
    ("6.1.4", "2-FAL", "Teor de compostos furânicos no óleo, gerados pelo envelhecimento do papel isolante; permite estimar o Grau de Polimerização."),
    ("6.2", "Indicadores", ""),
    ("6.2.1", "TG", "Total de Gases: soma de todos os gases dissolvidos analisados na cromatografia."),
    ("6.2.2", "TGC", "Total de Gases Combustíveis: soma de hidrogênio, metano, monóxido de carbono, etileno, etano e acetileno (IEEE C57.104)."),
    ("6.2.3", "GP", "Grau de Polimerização: número médio de monômeros das cadeias de celulose do papel isolante; quanto menor, mais envelhecida a isolação."),
    ("6.3", "Resultados", ""),
    ("6.3.1", "Máx. / Mín.", "Tipo de referência: o valor obtido deve ficar abaixo do máximo ou acima do mínimo indicado na norma do ensaio."),
    ("6.3.2", "% Máximo / % Mínimo", "Valor obtido em percentual da referência, usado nos gráficos; a referência corresponde a 100%."),
    ("6.3.3", "LD / LQ", "Limites de detecção e de quantificação do método do laboratório."),
    ("6.3.4", "ppm", "Partes por milhão, em massa (mg/kg)."),
    ("6.4",) + _CRITICIDADE,
    ("6.5", "OK / NC / NA", "Inspeção visual do transformador na coleta: Condição Normal, Não Conformidade ou Não Aplicável."),
)

GLOSSARIO_ELETRICO = (
    ("6.1", "Ensaios", ""),
    ("6.1.1", "R x T [TTR]", "Relação de Transformação: relação entre as tensões dos enrolamentos medida em cada fase, comparada com a relação nominal do TAP ensaiado."),
    ("6.1.2", "R x I", "Resistência de Isolação: resistência entre enrolamentos e entre cada enrolamento e a massa, medida em tensão contínua durante 10 minutos."),
    ("6.1.3", "R x O", "Resistência Ôhmica: resistência elétrica dos enrolamentos em corrente contínua, medida entre terminais."),
    ("6.2", "Termos", ""),
    ("6.2.1", "Relação Nominal", "Relação entre as tensões dos enrolamentos de alta e de baixa tensão no TAP ensaiado."),
    ("6.2.2", "Erro (%)", "Diferença percentual entre a relação medida e a nominal; admitido até ± 0,5% (ANSI/NETA ATS)."),
    ("6.2.3", "IP", "Índice de Polarização: resistência de isolação aos 600 s dividida pela resistência aos 60 s; conforme a partir de 1,0 (ANSI/NETA ATS)."),
    ("6.2.4", "IA", "Índice de Absorção: resistência de isolação aos 60 s dividida pela resistência aos 30 s."),
    ("6.2.5", "Medido / Calculado / Corrigido", "Resistência lida entre terminais; resistência por fase do enrolamento; e resistência por fase corrigida para 75 °C."),
    ("6.2.6", "AT / BT / Massa", "Enrolamento de alta tensão, enrolamento de baixa tensão e carcaça aterrada do transformador."),
    ("6.2.7", "TAP", "Posição do comutador em que os ensaios foram realizados."),
    ("6.3",) + _CRITICIDADE,
)

CONSIDERACOES_OLEO = (
    "Os resultados representam a condição do óleo isolante na data da coleta e dependem da representatividade da amostra; por isso o ponto de coleta, o fluido e as condições ambientes ficam registrados na ficha de coleta.",
    "Cada valor é comparado com a referência da norma indicada na ficha. Resultado fora da referência deve ser avaliado junto com o histórico do equipamento e com os demais ensaios antes de qualquer intervenção.",
    "Recomenda-se manter a periodicidade de coleta indicada em cada ficha, para acompanhar a evolução dos resultados ao longo das campanhas.",
)

CONSIDERACOES_ELETRICO = (
    "Os ensaios são realizados com o transformador desenergizado e aterrado, nas condições de temperatura e umidade registradas na ficha de registro.",
    "A resistência ôhmica é corrigida para 75 °C e a relação de transformação é comparada com a relação nominal do TAP ensaiado; a comparação com ensaios anteriores e com os valores de fábrica completa o diagnóstico.",
    "Recomenda-se manter a periodicidade indicada em cada ficha, para acompanhar a evolução dos resultados ao longo das campanhas.",
)


# ------------------- Fluidos lubrificantes e hidráulicos --------------------
# Proposta de 01/10/2026 (validar com o cliente): mesma estrutura de carta das
# outras tecnologias, com os ensaios FQ, EF e CP. Nenhuma norma de outra técnica.
CONTEUDO_FLUIDO = (
    "Seção A – Carta ao Cliente",
    "Seção B – KPI’s Dashboard",
    "Seção C – Relação de Equipamentos Contemplados",
    "Seção D – Fichas da Análise de Fluidos [coleta da amostra e resultados FQ, EF e CP]",
)

GLOSSARIO_FLUIDO = (
    ("6.1", "Ensaios", ""),
    ("6.1.1", "FQ", "Físico-Química: propriedades do fluido — viscosidade cinemática a 40 °C (e a 100 °C, quando contratada), teor de água, número de acidez (TAN), aparência e demais parâmetros informados pelo laboratório."),
    ("6.1.2", "EF", "Espectrofotometria (análise elementar): teor dos elementos químicos dissolvidos ou em suspensão fina no fluido, em ppm — metais de desgaste, contaminantes e elementos dos aditivos."),
    ("6.1.3", "CP", "Contagem de Partículas: quantidade de partículas sólidas por mL nos tamanhos > 4, > 6 e > 14 µm(c), que forma o código de limpeza ISO 4406. Solicitada por padrão nos fluidos hidráulicos."),
    ("6.2", "Termos", ""),
    ("6.2.1", "cSt", "Centistokes (mm²/s): unidade da viscosidade cinemática."),
    ("6.2.2", "TAN", "Número de acidez total, em mgKOH/g: o aumento em relação ao óleo novo indica oxidação ou contaminação."),
    ("6.2.3", "ppm", "Partes por milhão, em massa (mg/kg)."),
    ("6.2.4", "ISO 4406", "Código de limpeza X/Y/Z: um número de escala para cada tamanho de partícula (> 4, > 6 e > 14 µm(c)); cada grau a mais corresponde a aproximadamente o dobro de partículas."),
    ("6.2.5", "Meta de limpeza", "Código ISO 4406 alvo do sistema, definido para o equipamento, o fabricante ou o contrato. Sem meta cadastrada, o código é informado sem classificação."),
    ("6.2.6", "Referência", "Limite de alerta e de crítico de cada parâmetro, com a origem (norma, fabricante, laboratório, acordo ou óleo novo) e a vigência. Sem referência cadastrada, o valor é informado sem classificação."),
    ("6.2.7", "Tendência", "Evolução do parâmetro nas coletas anteriores do mesmo equipamento; um resultado isolado não basta para um diagnóstico definitivo."),
    ("6.3", "Situação", ""),
    ("6.3.1", "Rotina", "Resultado dentro das referências: manter a periodicidade de coleta."),
    ("6.3.2", "Alerta", "Resultado além do limite de alerta, ou código de limpeza acima da meta: investigar a causa e intensificar o monitoramento."),
    ("6.3.3", "Crítica", "Resultado além do limite crítico: intervenção recomendada no prazo indicado na ficha."),
    ("6.3.4", "LD / LQ", "Limites de detecção e de quantificação do método do laboratório."),
)

CONSIDERACOES_FLUIDO = (
    "Os resultados representam a condição do fluido na data da coleta e dependem da representatividade da amostra; por isso o ponto de coleta, a condição operacional e o histórico do fluido (horas, trocas, complementos e filtros) ficam registrados na ficha de coleta.",
    "Cada resultado é avaliado pela referência cadastrada para o equipamento, o fluido ou o contrato, e pela tendência das coletas anteriores. Resultado isolado fora da referência deve ser confirmado com o histórico e, quando necessário, com nova amostragem antes de uma intervenção.",
    "Recomenda-se manter a periodicidade de coleta indicada em cada ficha, para acompanhar a evolução dos resultados ao longo das campanhas.",
)
