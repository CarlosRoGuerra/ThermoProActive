"""
Conteúdo da Carta ao Cliente da Termografia — transcrito do relatório de
referência do cliente RT.TE-2026.02.12.02307 (Acco Brands – Foroni), itens 6 e 7.

O item 6.11 (Fluxo de Trabalho) do relatório antigo não entra aqui: cita o
e-MasterSys e, no modelo novo, o fluxo sai no item 7 (Definição da Técnica),
cadastrado na tecnologia. Entradas sem texto são títulos de grupo (6.1, 6.2).
"""

GLOSSARIO_TERMOGRAFIA = (
    ("6.1", "Temperaturas", ""),
    ("6.1.1", "T.M.", "Temperatura Monitorada: É a temperatura mensurada do objeto foco da medição que apresenta diferencial de temperatura em relação à temperatura de referência, oferecendo determinado grau de risco."),
    ("6.1.2", "T.R.", "Temperatura de Referência: É a temperatura mensurada de objeto similar, sem incidência de anomalia, submetido as mesmas condições de trabalho e carga em relação ao objeto foco da medição."),
    ("6.1.3", "ΔT", "Delta de Temperatura: É a diferença matemática da temperatura monitorada em relação à temperatura de referência."),
    ("6.1.4", "M.T.A.", "Máxima Temperatura Admissível: São valores obtidos através de especificações técnicas de componentes junto a fabricantes e referências da IEEC (International Electrical Engineering Conference)."),
    ("6.1.5", "C.T.M.", "Correção da Temperatura Monitorada: Aplica-se nos casos em que o objeto monitorado apresenta corrente elétrica de trabalho inferior a corrente nominal dele."),
    ("6.2", "Grandezas Elétricas", ""),
    ("6.2.1", "I(t)", "Corrente Elétrica de Trabalho: É a corrente elétrica mensurada em cada fase do objeto foco da medição; espera-se equilíbrio de carga entre as fases do circuito elétrico. Tolerância de ± 5,0%."),
    ("6.2.2", "I(n)", "Corrente Elétrica Nominal: É a corrente elétrica nominal do objeto monitorado."),
    ("6.2.3", "U(t)", "Tensão Elétrica de Trabalho: É a tensão elétrica mensurada em cada fase do objeto monitorado; espera-se equilíbrio de tensão entre as fases do circuito elétrico. Tolerância de ± 5,0%."),
    ("6.2.4", "U(n)", "Tensão Elétrica Nominal: É a tensão elétrica nominal do objeto monitorado."),
    ("6.3", "O.S.P.", "Ordem de Serviço Preditivo: ordem de serviço gerada para correção de cada anomalia detectada."),
    ("6.4", "G.R.", "Grau de Risco: Determina o prazo de correção das anomalias detectadas. Estão fundamentados em 3 aspectos principais, na M.T.A., no ΔT, e na experiência do inspetor-analista."),
    ("6.4.1", "GR-1", "Grau de Risco N°.01: Risco eminente. Recomenda-se intervenção imediata pela equipe de manutenção, prazo máximo de 03 dias. Em casos extremos o inspetor poderá solicitar o reparo em caráter de urgência. ΔT > 100,0°C."),
    ("6.4.2", "GR-2", "Grau de Risco N°.02: Risco elevado. Recomenda-se intervenção pela equipe de manutenção em prazo máximo de 10 dias. ΔT > 60,0°C e ≤ 100,0°C."),
    ("6.4.3", "GR-3", "Grau de Risco N°.03: Risco moderado. Recomenda-se intervenção pela equipe de manutenção em prazo máximo de 20 dias. ΔT > 20,0°C e ≤ 60,0°C."),
    ("6.4.4", "GR-4", "Grau de Risco N°.04: Risco baixo. Recomenda-se intervenção pela equipe de manutenção em prazo máximo de 30 dias. ΔT ≤ 20,0°C."),
    ("6.5", "IC", "Insuficiência de Carga: Carga igual ou menor que 70,0%. Aquecimentos podem ficar não visíveis ao sistema de detecção de infravermelho devido a insuficiência de carga."),
    ("6.6", "MP", "Monitoramento Prejudicado: Ocorre nos casos em que existe nível de obstrução parcial, física ou não, ao objeto foco da medição. É interessante avaliar o nível de obstrução juntamente com o departamento de manutenção e segurança do trabalho."),
    ("6.7", "NM", "Não Monitorado: Ocorre nos casos em que existe nível de obstrução total, física ou não, ao objeto foco da medição; e/ou que coloque em risco a integridade física dos trabalhadores. É interessante avaliar o nível de obstrução juntamente com o departamento de manutenção e segurança do trabalho, e/ou criar condição segura aos colaboradores."),
    ("6.8", "OK", "Normalidade Operacional: Carga maior que 70,0%. Os circuitos carregados não apresentam anomalias térmicas. Recomenda-se nova inspeção em período máximo de 90 dias."),
    ("6.9", "PDM", "Parado Devido à Manutenção: Equipamento encontra-se parado devido algum tipo de intervenção da equipe de manutenção."),
    ("6.10", "PDP", "Parado Devido ao Processo: Equipamento encontra-se parado devido o processo produtivo."),
)

CONSIDERACOES_TERMOGRAFIA = (
    "Os critérios considerados nas análises das anomalias detectadas são técnicos, associados com a vasta experiência do analista que realizará um diagnóstico preciso referente à condição térmica na qual o objeto foco da medição está submetido. Porém, vale lembrar que cada equipamento tem seu nível de importância e criticidade para a planta onde está instalado, e deverá ser levado em consideração pelo e planejamento e controle da manutenção durante a elaboração do plano de corretivas baseadas nas preditivas.",
    "Toda anomalia detectada deverá ser corrigida o mais rápido possível, pois o prazo sugerido serve apenas como referência, haja vista que a avaliação termográfica não é executada mensalmente (caso sua planta realize avaliação mensal, desconsiderar este item).",
)
