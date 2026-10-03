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
    "Seção D – Ordens de Serviços Preditivos [coleta da amostra e resultados FQ, EF e CP]",
)

GLOSSARIO_FLUIDO = (
    # Graus de risco, prazos e condições: como no relatório-modelo do laboratório
    # (2016-11-0882). A regra que calcula o GR pelas referências está em grau_risco_fluidos.py.
    ("6.1", "O.S.P.", "Ordem de Serviço Preditivo gerada para correção de cada anomalia detectada."),
    ("6.2", "G.R.", "Grau de Risco: determinam o prazo de correção das anomalias detectadas."),
    ("6.2.1", "GR-1", "Grau de Risco N°.01: Risco iminente. Recomenda-se intervenção imediata pela equipe de manutenção em prazo máximo de 03 dias. Em casos extremos o inspetor poderá solicitar o reparo em caráter de urgência. Anomalias observadas a olho nu."),
    ("6.2.2", "GR-2", "Grau de Risco N°.02: Risco elevado. Recomenda-se intervenção pela equipe de manutenção em prazo máximo de 30 dias. Anomalias observadas em mais de 02 ensaios."),
    ("6.2.3", "GR-3", "Grau de Risco N°.03: Risco moderado. Recomenda-se intervenção pela equipe de manutenção em prazo máximo de 60 dias. Anomalias observadas em 02 ensaios."),
    ("6.2.4", "GR-4", "Grau de Risco N°.04: Risco baixo. Recomenda-se intervenção pela equipe de manutenção em parada programada, prazo máximo de 90 dias. Anomalia observada em apenas 01 ensaio."),
    ("6.3", "MP", "Monitoramento Prejudicado: ocorre em casos onde há existência de obstrução parcial ao ponto de coleta ou aos equipamentos a serem monitorados. É interessante avaliar o nível de obstrução juntamente com o departamento de segurança do trabalho, sendo possível programar a desobstrução temporária. Recomenda-se nova inspeção o mais rápido possível."),
    ("6.4", "NM", "Não Monitorado: ocorre em casos onde há existência de obstrução total ao ponto de coleta ou aos equipamentos a serem monitorados, e/ou que coloque em risco a integridade física dos trabalhadores. É interessante avaliar a possibilidade de desobstrução juntamente com o departamento de segurança do trabalho e/ou criar condição segura aos trabalhadores. Recomenda-se nova inspeção o mais rápido possível."),
    ("6.5", "OK / GR-0", "Normalidade Operacional: nenhum ensaio com anomalia. Recomenda-se nova inspeção em período máximo de 03 meses."),
    ("6.6", "PDM", "Parado Devido Manutenção: equipamento encontra-se parado devido algum tipo de intervenção da equipe de manutenção."),
    ("6.7", "PDP", "Parado Devido Processo: equipamento encontra-se parado devido anormalidades do processo produtivo."),
    ("6.8", "FQ", "Ensaio Físico-Químico: propriedades do fluido e o seu estado de degradação."),
    ("6.8.1", "Viscosidade", "Mede a resistência de fluxo de escoamento do lubrificante e é considerada uma das características físicas mais importantes. É medida em Centistokes (cSt), às temperaturas de 40°C e/ou 100°C, dependendo do lubrificante."),
    ("6.8.2", "Água", "Sua presença no óleo diminui a lubrificação, impede a ação de aditivos e promove a oxidação. O teor de água no óleo pode ser determinado por crepitação, destilação, infravermelho ou por Karl Fischer, e é relatado em partes por milhão (ppm) ou em percentual. A técnica utilizada depende do tipo de lubrificante."),
    ("6.8.3", "TAN", "Número Total de Ácidos: indica a medida de ácidos presentes no lubrificante. É medido em miligramas de hidróxido de potássio por grama (mgKOH/g). Números maiores que o do lubrificante novo indicam oxidação ou alguns tipos de contaminação."),
    ("6.8.4", "TBN", "Número Total de Base: indica a medida de alcalinidade do óleo lubrificante, ou a capacidade de neutralizar o ácido. É medido em miligramas de hidróxido de potássio por grama (mgKOH/g). É utilizado em óleo de motores."),
    ("6.8.5", "Insol. Pent.", "Insolúveis em pentano: relatados em percentual em massa (% p/p)."),
    ("6.9", "EF", "Ensaio Espectrofotométrico: o ensaio de metais por ICP (plasma indutivamente acoplado) detecta os metais a seguir, medindo menos de 8 µm de tamanho, que podem estar presentes no óleo usado devido ao desgaste, contaminação ou aditivos. Resultado em ppm (mg/kg)."),
    ("6.9.1", "Metais de desgaste", "Alumínio, cobre, cromo, ferro, chumbo, estanho, níquel, prata, manganês, titânio e vanádio."),
    ("6.9.2", "Metais contaminantes", "Silício, sódio, boro e potássio."),
    ("6.9.3", "Metais aditivos", "Zinco, molibdênio, cálcio, bário, magnésio e fósforo."),
    ("6.10", "CP", "Ensaio de Contagem de Partículas."),
    ("6.10.1", "Resultados", "Obtidos segundo as normas ISO 4406 / NAS 1638 / AS 4059, determinam o grau de limpeza requerido. O código ISO 4406 é formado pelos números de escala das partículas > 4, > 6 e > 14 µm(c) por mL; cada grau a mais corresponde a aproximadamente o dobro de partículas."),
    ("6.10.2", "Particulado", "Quantidade de partículas encontrada na amostra referente a sua morfologia. É medida em micra (µm). Contagem em até 6 tamanhos diferentes (> 4, > 6, > 14, > 21, > 38 e > 70)."),
    ("6.11", "Meta de limpeza", "Código ISO 4406 alvo do sistema, definido para o equipamento, o fabricante ou o contrato. Sem meta cadastrada, o código é informado sem classificação."),
    ("6.12", "Referência", "Limite de alerta e de crítico de cada parâmetro, com a origem (norma, fabricante, laboratório, acordo ou óleo novo) e a vigência. Sem referência cadastrada, o valor é informado sem classificação."),
    ("6.13", "Tendência", "Evolução do parâmetro nas coletas anteriores do mesmo equipamento; um resultado isolado não basta para um diagnóstico definitivo."),
    ("6.14", "Status", "Resultado de cada ensaio frente às referências cadastradas:"),
    ("6.14.1", "OK", "Rotina — resultado dentro das referências (não necessita intervenção)."),
    ("6.14.2", "ATENÇÃO", "Alerta — resultado além do limite de alerta, ou código de limpeza acima da meta (intensificar monitoramento)."),
    ("6.14.3", "INTERVIR", "Crítica — resultado além do limite crítico (atenção imediata)."),
    ("6.14.4", "LD / LQ", "Limites de detecção e de quantificação do método do laboratório."),
)

CONSIDERACOES_FLUIDO = (
    "Os critérios considerados nas análises das anomalias detectadas são técnicos, baseados nas referências cadastradas para o equipamento, o fluido ou o contrato. Nossa equipe fornecerá diagnóstico preciso referente às condições nas quais o objeto avaliado está submetido, porém vale lembrar que cada equipamento tem seu nível de importância individual para a planta onde está instalado, e deverá ser levado em consideração pelo controle e planejamento da manutenção durante a elaboração do plano de correção.",
    "Toda anomalia detectada deverá ser corrigida o mais rápido possível, pois o prazo sugerido serve apenas como referência, haja vista que a avaliação não é executada mensalmente (caso sua planta realize avaliação mensal, desconsiderar este item).",
    "Os resultados representam a condição do fluido na data da coleta e dependem da representatividade da amostra; por isso o ponto de coleta, a condição operacional e o histórico do fluido (horas, trocas, complementos e filtros) ficam registrados na ficha de coleta.",
    "Resultado isolado fora da referência deve ser confirmado com o histórico e, quando necessário, com nova amostragem antes de uma intervenção. Recomenda-se manter a periodicidade de coleta indicada em cada ficha, para acompanhar a evolução dos resultados ao longo das campanhas.",
)
