"""
Carta da inspeção genérica — tecnologia de inspeção por rota sem medições
específicas (ex.: Análise Sensitiva Sensorial), escolhida de propósito no
cadastro (`ModuloTecnico.INSPECAO_GENERICA`).

Mesmos termos do modelo Word aprovado (OSP, Graus de Risco e prazos, MP, NM, PDM,
PDP), sem o que é de outra técnica: o "OK" do modelo fala de carga e anomalia
térmica (termografia) e LA/LOA são pontos de medição de vibração — aqui não
entram. As considerações falam da condição do objeto avaliado, não da
"condição dinâmica".
"""
from .inspecao import CARTA_CONSIDERACOES, CARTA_GLOSSARIO

# OSP, Grau de Risco (6.2.1–6.2.4), MP e NM — iguais ao modelo Word.
_COMUNS = {"6.1", "6.2", "6.2.1", "6.2.2", "6.2.3", "6.2.4", "6.3", "6.4"}

GLOSSARIO_GENERICO = tuple(t for t in CARTA_GLOSSARIO if t[0] in _COMUNS) + (
    ("6.5", "OK", "Normalidade Operacional: o equipamento não apresenta anomalia na técnica aplicada."),
    ("6.6", "PDM", "Parado Devido Manutenção: Equipamento encontra-se parado devido algum tipo de intervenção da equipe de manutenção;"),
    ("6.7", "PDP", "Parado Devido Processo: Equipamento encontra-se parado devido anormalidades do processo produtivo."),
)

CONSIDERACOES_GENERICAS = (
    "Os critérios considerados nas análises das anomalias detectadas são técnicos, associados com a vasta experiência do analista que dará diagnóstico preciso referente à condição na qual o objeto avaliado está submetido, porém vale lembrar que cada equipamento tem seu nível de criticidade para a planta onde está instalado, e deverá ser levado em consideração pelo controle e planejamento da manutenção durante a elaboração do plano de manutenções corretivas baseadas pela manutenção preditiva.",
    *CARTA_CONSIDERACOES[1:],
)
