"""
Vínculo Análise técnica → OSP da manutenção corretiva.

O ciclo preditivo abre a OSP quando o escritório CONFIRMA o achado
(`AchadoSerializer.update`). Na corretiva por rota não existe essa etapa: o
documento que sai para o cliente é a própria folha da intervenção executada, e
ela precisa de um número de OSP. O gatilho, portanto, é o salvamento da análise
técnica — não o clique em "Analisar", que só abre um `ServicoCampo` vazio.

A geração continua sendo exclusividade de `OrdemServico.gerar_de_achado`
(numeração, sequenciais, GR e cópia dos dados técnicos): aqui só se decide
QUANDO chamá-la e a quem amarrar o resultado.
"""


def vincular_osp_da_analise(servico):
    """
    Garante 1 OSP para a análise técnica desta intervenção — idempotente.

    Devolve a OSP vinculada (ou `None` quando ainda não há análise técnica).
    NÃO salva o serviço: quem chama está dentro de uma transação e grava o
    `ServicoCampo` uma única vez, junto das demais alterações.

    Dois vínculos diferentes, que não se misturam:

    * `ServicoCampo.osp` — a OSP desta intervenção. Quando o serviço nasceu da
      execução de uma OSP preditiva já aberta ("OSP de origem"), é ela que
      responde pelo trabalho: gerar outra duplicaria a mesma ordem.
    * `ServicoCampo.achado` — a análise de ORIGEM do fluxo preditivo. Nunca é
      sobrescrita aqui; a análise da própria intervenção é `analise_tecnica`.
    """
    achado = servico.analise_tecnica
    if achado is None:
        return None
    if servico.osp_id:
        return servico.osp
    from apps.osp.models import OrdemServico  # tardio: evita ciclo servicos↔osp

    servico.osp = OrdemServico.gerar_de_achado(achado)
    return servico.osp
