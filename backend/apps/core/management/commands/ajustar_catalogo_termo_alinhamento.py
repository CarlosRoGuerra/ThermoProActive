# -*- coding: utf-8 -*-
"""
Ajusta o catálogo de tecnologias para os relatórios de termografia mecânica e de alinhamento a laser.

O que faz (idempotente: rodar de novo não muda nada depois da primeira vez):

  1. Termografia de sistemas mecânicos — `TI-SMD` e `TI-SME` passam a usar o módulo
     `TERMOGRAFIA_MECANICA`; `TI-PI` passa a usar `TERMO_PROCESSOS`. Até aqui apontavam para o
     módulo elétrico (`TERMOGRAFIA`) e o relatório saía com glossário e layout da elétrica.
  2. Alinhamento entre polias — cria a tecnologia `ALEP` com o módulo `ALINHAMENTO_POLIAS`, se
     ela não existir. O `tipo_corretiva` é o mesmo da tecnologia de eixos (`ALEE`), lida do banco
     no momento da execução; nada é inventado.

O que NÃO faz: não cria critério de tolerância nem de ΔT (isso é cadastro do Master, na tela
Dados do sistema → Limites de alarme de série), não altera medições, não apaga nada.

Os catálogos locais podem ter nomes/siglas repetidos (cópia da produção): a busca usa a sigla ou o
módulo e reaproveita o registro mais antigo, nunca `get_or_create` por nome.

Uso:
    python manage.py ajustar_catalogo_termo_alinhamento --dry-run   # só mostra o que mudaria
    python manage.py ajustar_catalogo_termo_alinhamento             # aplica

Produção: NÃO rodar sem autorização do responsável pelo projeto (ver docs/26).
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.cadastros.models import ModuloTecnico, TecnologiaAnalise

# sigla → módulo esperado (a sigla é a chave do catálogo do cliente).
TERMOGRAFIA_POR_SIGLA = {
    "TI-SMD": ModuloTecnico.TERMOGRAFIA_MECANICA,
    "TI-SME": ModuloTecnico.TERMOGRAFIA_MECANICA,
    "TI-PI": ModuloTecnico.TERMO_PROCESSOS,
}
SIGLA_POLIAS = "ALEP"
NOME_POLIAS = "Alinhamento à Laser Entre Polias"


class Command(BaseCommand):
    help = "Aponta TI-SMD/TI-SME/TI-PI para os módulos mecânicos e cria a tecnologia de alinhamento entre polias."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Mostra as mudanças sem gravar nada.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        w = self.stdout.write
        planos = []  # (descrição, função que aplica)

        for sigla, modulo in TERMOGRAFIA_POR_SIGLA.items():
            tec = TecnologiaAnalise.objects.filter(sigla=sigla).order_by("id").first()
            if tec is None:
                w(self.style.WARNING(f"  {sigla}: tecnologia não encontrada — nada a ajustar."))
                continue
            if tec.modulo_tecnico == modulo.value:
                w(f"  {sigla}: já usa {modulo.value}.")
                continue
            planos.append((
                f"  {sigla} (#{tec.pk}): módulo «{tec.modulo_tecnico or '—'}» → «{modulo.value}»",
                self._aplicar_modulo(tec, modulo.value),
            ))

        eixos = TecnologiaAnalise.objects.filter(modulo_tecnico=ModuloTecnico.ALINHAMENTO_EIXOS.value) \
            .order_by("id").first()
        if eixos is None:
            raise CommandError("Não há tecnologia com o módulo ALINHAMENTO_EIXOS (ALEE). Crie-a antes.")
        polias = TecnologiaAnalise.objects.filter(modulo_tecnico=ModuloTecnico.ALINHAMENTO_POLIAS.value) \
            .order_by("id").first()
        if polias is None:
            planos.append((
                f"  {SIGLA_POLIAS}: criar «{NOME_POLIAS}», módulo ALINHAMENTO_POLIAS, "
                f"análise corretiva «{eixos.tipo_corretiva or '—'}» (igual à de eixos, #{eixos.pk})",
                self._criar_polias(eixos),
            ))
        elif polias.tipo_corretiva != eixos.tipo_corretiva:
            planos.append((
                f"  {polias.sigla or '#' + str(polias.pk)}: análise corretiva «{polias.tipo_corretiva or '—'}» "
                f"→ «{eixos.tipo_corretiva or '—'}» (igual à de eixos)",
                self._aplicar_corretiva(polias, eixos.tipo_corretiva),
            ))
        else:
            w(f"  alinhamento entre polias (#{polias.pk}): já cadastrado e coerente com eixos.")

        if not eixos.tipo_corretiva:
            w(self.style.WARNING(
                "  Aviso: a tecnologia de eixos (ALEE) está sem análise corretiva. A polias segue o mesmo "
                "critério (vazio). Definir ALINHAMENTO como análise corretiva depende de o fluxo corretivo "
                "de alinhamento existir (hoje só o balanceamento tem)."))

        if not planos:
            w(self.style.SUCCESS("Catálogo já está ajustado. Nada a fazer."))
            return
        w("Mudanças:" if dry else "Aplicando:")
        for descricao, _ in planos:
            w(descricao)
        if dry:
            w(self.style.WARNING("--dry-run: nada foi gravado."))
            return
        with transaction.atomic():
            for _, aplicar in planos:
                aplicar()
        w(self.style.SUCCESS(f"{len(planos)} ajuste(s) aplicado(s)."))

    @staticmethod
    def _aplicar_modulo(tec, modulo):
        def aplicar():
            tec.modulo_tecnico = modulo
            tec.save(update_fields=["modulo_tecnico"])
        return aplicar

    @staticmethod
    def _aplicar_corretiva(tec, tipo):
        def aplicar():
            tec.tipo_corretiva = tipo
            tec.save(update_fields=["tipo_corretiva"])
        return aplicar

    @staticmethod
    def _criar_polias(eixos):
        def aplicar():
            TecnologiaAnalise.objects.create(
                nome=NOME_POLIAS, sigla=SIGLA_POLIAS, modulo_tecnico=ModuloTecnico.ALINHAMENTO_POLIAS.value,
                tipo_corretiva=eixos.tipo_corretiva,
            )
        return aplicar
