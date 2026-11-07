"""
Regressão A-07 — o servidor não sobe em produção com configuração insegura.

Testa a função pura e, num processo separado, o import real do `config.settings` (o teste roda
com DEBUG ligado, então o ramo de produção só se exercita assim).
"""
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

from config.seguranca import problemas_de_configuracao

BACKEND = Path(__file__).resolve().parents[2]
CHAVE_BOA = "k3Jx9-Qm2vLw8RzTn5YbHcD7sFpA1eUoGiXyZ4tN6BhVjWqM0aSdCfE_rKlPuOg"


class FuncaoDeValidacao(SimpleTestCase):
    def problemas(self, **kw):
        base = {"debug": False, "secret_key": CHAVE_BOA, "allowed_hosts": ["app.exemplo.com.br", "backend"]}
        return problemas_de_configuracao(**{**base, **kw})

    def test_config_boa_passa_e_debug_nao_valida_nada(self):
        self.assertEqual(self.problemas(), [])
        self.assertEqual(self.problemas(debug=True, secret_key="", allowed_hosts=["*"]), [])

    def test_recusa_chaves_conhecidas_curtas_ou_ausentes(self):
        for chave in ("", "dev-insecure-change-me-em-producao", "docker-dev-secret-troque-em-producao",
                      "TROQUE-POR-UMA-CHAVE-ALEATORIA-LONGA", "curta", "a" * 64):
            self.assertTrue(self.problemas(secret_key=chave), chave)

    def test_recusa_allowed_hosts_vazio_ou_curinga(self):
        self.assertTrue(self.problemas(allowed_hosts=[]))
        self.assertTrue(self.problemas(allowed_hosts=["*"]))
        self.assertTrue(self.problemas(allowed_hosts=["app.com", "*"]))


class ImportDoSettings(SimpleTestCase):
    def importar(self, **env_extra):
        env = {k: v for k, v in os.environ.items() if k not in ("DEBUG", "SECRET_KEY", "ALLOWED_HOSTS", "DATABASE_URL")}
        env.update({"PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(BACKEND), **env_extra})
        return subprocess.run(
            [sys.executable, "-W", "ignore", "-c", "import config.settings as s; print('OK', s.DEBUG)"],
            cwd=BACKEND, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            # Sem stdin herdado: no Windows, sob carga, o pipe do runner às vezes devolvia stderr=None.
            stdin=subprocess.DEVNULL,
        )

    def test_producao_com_chave_padrao_nao_sobe(self):
        r = self.importar(DEBUG="False", SECRET_KEY="dev-insecure-change-me-em-producao", ALLOWED_HOSTS="a.com")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("ImproperlyConfigured", r.stderr or "")

    def test_container_com_banco_e_sem_debug_e_tratado_como_producao(self):
        r = self.importar(DATABASE_URL="postgres://u:p@db:5432/x")  # sem DEBUG/SECRET_KEY
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("SECRET_KEY", r.stderr or "")

    def test_producao_correta_e_desenvolvimento_local_sobem(self):
        ok = self.importar(DEBUG="False", SECRET_KEY=CHAVE_BOA, ALLOWED_HOSTS="a.com,backend")
        self.assertEqual(ok.returncode, 0, ok.stderr or "")
        self.assertIn("OK False", ok.stdout or "")
        dev = self.importar()  # SQLite local, sem nada no ambiente
        self.assertEqual(dev.returncode, 0, dev.stderr or "")
        self.assertIn("OK True", dev.stdout or "")
