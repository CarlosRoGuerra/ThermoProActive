"""
Validação de boot das configurações sensíveis (achado A-07).

Roda no import do `settings.py` quando `DEBUG=False`: um servidor de produção
não sobe com a chave pública do repositório, com `ALLOWED_HOSTS=*` ou com
valores de exemplo do `.env.prod.example`. Função pura (sem Django) para ser
testável sem reimportar o settings.
"""

#: Trechos que denunciam chave de exemplo/desenvolvimento (comparação em minúsculas).
SEGREDOS_CONHECIDOS = (
    "dev-insecure", "django-insecure", "docker-dev-secret", "troque", "change-me", "changeme",
    "troque-por", "secret_key", "your-secret", "example", "exemplo", "senha", "password",
)
TAMANHO_MINIMO_SECRET_KEY = 32


def problemas_de_configuracao(*, debug: bool, secret_key: str, allowed_hosts) -> list[str]:
    """Lista de motivos pelos quais a configuração NÃO serve para produção ([] = ok)."""
    if debug:
        return []
    problemas = []
    chave = (secret_key or "").strip()
    if not chave:
        problemas.append("SECRET_KEY ausente.")
    else:
        minusculas = chave.lower()
        if any(trecho in minusculas for trecho in SEGREDOS_CONHECIDOS):
            problemas.append("SECRET_KEY é um valor de exemplo/desenvolvimento conhecido.")
        if len(chave) < TAMANHO_MINIMO_SECRET_KEY or len(set(chave)) < 10:
            problemas.append(
                f"SECRET_KEY fraca (mínimo {TAMANHO_MINIMO_SECRET_KEY} caracteres e variedade). "
                'Gere com: python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
    hosts = [h.strip() for h in (allowed_hosts or []) if h and h.strip()]
    if not hosts:
        problemas.append("ALLOWED_HOSTS vazio: informe o domínio/IP do servidor.")
    if any(h == "*" or h == ".*" for h in hosts):
        problemas.append("ALLOWED_HOSTS contém '*': liste apenas os hosts reais.")
    return problemas
