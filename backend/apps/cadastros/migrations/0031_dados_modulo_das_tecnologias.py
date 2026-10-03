"""
Fim do "módulo padrão = vibração": cada tecnologia que estava sem módulo e que
já tem uso recebe um módulo EXPLÍCITO, para nada mudar de dono em silêncio.

Só mexe em `modulo_tecnico` vazio, nesta ordem:

1. `tipo_corretiva = BALANCEAMENTO` → BALANCEAMENTO. O relatório de balanceamento
   continua igual ao de hoje (tabela de severidade na carta: o veredito do
   balanceamento é a zona de vibração), agora por escolha declarada.
2. Sigla AFLH (Análise de Fluídos Lubrificantes e Hidráulicos) → FLUIDO_LUBRIFICANTE,
   o módulo novo desta etapa.
3. Sigla ALEE (Alinhamento a Laser Entre Eixos) → ALINHAMENTO_EIXOS — planejado:
   relatório "não implementado", em vez de sair com o layout da vibração.
4. Tecnologia que já tem relatório emitido → INSPECAO_GENERICA: os relatórios
   continuam abrindo, sem a tabela ISO-10816 nem o bloco de amplitudes, que eram
   da vibração (hoje: Análise Sensitiva Sensorial).

As demais continuam vazias: o relatório só sai depois que o Master escolher o
módulo em Cadastros → Tecnologias de análise. As siglas são as do catálogo da
produção (associação explícita, uma vez, como na 0026 — nada é deduzido pelo
nome em tempo de execução).
"""
from django.db import migrations

POR_SIGLA = {"AFLH": "FLUIDO_LUBRIFICANTE", "ALEE": "ALINHAMENTO_EIXOS"}


def carregar(apps, schema_editor):
    Tecnologia = apps.get_model("cadastros", "TecnologiaAnalise")
    Relatorio = apps.get_model("coletas", "Relatorio")
    com_relatorio = set(Relatorio.objects.values_list("tecnologia_id", flat=True))
    for tec in Tecnologia.objects.filter(modulo_tecnico=""):
        if tec.tipo_corretiva == "BALANCEAMENTO":
            modulo = "BALANCEAMENTO"
        elif (tec.sigla or "").strip().upper() in POR_SIGLA:
            modulo = POR_SIGLA[tec.sigla.strip().upper()]
        elif tec.id in com_relatorio:
            modulo = "INSPECAO_GENERICA"
        else:
            continue
        Tecnologia.objects.filter(pk=tec.pk).update(modulo_tecnico=modulo)


def desfazer(apps, schema_editor):
    # Volta ao vazio só o que esta migração preencheu (e nada que já tinha módulo antes).
    apps.get_model("cadastros", "TecnologiaAnalise").objects.filter(
        modulo_tecnico__in=["BALANCEAMENTO", "FLUIDO_LUBRIFICANTE", "ALINHAMENTO_EIXOS", "INSPECAO_GENERICA"],
    ).update(modulo_tecnico="")


class Migration(migrations.Migration):
    dependencies = [
        ("cadastros", "0030_modulos_tecnicos_explicitos"),
        ("coletas", "0010_carregamento_tipo_corretiva"),
    ]

    operations = [migrations.RunPython(carregar, desfazer)]
