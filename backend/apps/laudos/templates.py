"""Textos declarativos nos espaços existentes; o desenho do PDF é preservado."""
import re
from django.core.exceptions import ValidationError

SECOES = ["capa", "diagnostico", "recomendacoes", "conclusao", "evidencias", "comparativos"]
OBRIGATORIAS = {"capa", "diagnostico", "recomendacoes", "conclusao"}


def validar_configuracao(configuracao):
    if not isinstance(configuracao, dict) or set(configuracao) - {"titulo_documento", "rodape", "secoes"}:
        raise ValidationError("Use somente título, rodapé e ordem de seções declarativas.")
    for campo, limite in (("titulo_documento", 200), ("rodape", 100)):
        texto = configuracao.get(campo, "")
        if not isinstance(texto, str) or len(texto) > limite or re.search(r"<[^>]+>", texto):
            raise ValidationError(f"{campo}: informe texto simples com até {limite} caracteres, sem HTML.")
    secoes = configuracao.get("secoes", SECOES)
    if not isinstance(secoes, list) or any(not isinstance(s, str) or s not in SECOES for s in secoes):
        raise ValidationError("Informe uma lista de seções conhecidas.")
    if len(secoes) != len(set(secoes)) or not OBRIGATORIAS.issubset(secoes):
        raise ValidationError("Inclua capa, diagnóstico, recomendações e conclusão, sem seções repetidas.")
    if secoes != SECOES:
        raise ValidationError("O PDF preserva todas as seções e a ordem do layout existente. Personalize os textos nos espaços disponíveis.")
    return configuracao
