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


def osp_da_intervencao(achado, servico=None):
    """
    A OSP que representa esta intervenção — usada tanto na folha do relatório
    quanto na tela de Análise final. Uma regra só, duas fontes possíveis:

    1. `achado.osp` — o vínculo direto (`OrdemServico.achado`), presente quando
       esta própria análise gerou a OSP.
    2. `ServicoCampo.osp`, quando o vínculo direto está vazio — cobre a
       intervenção que herdou uma OSP de origem (execução de uma OSP preditiva
       já aberta): `vincular_osp_da_analise` não reatribui `OrdemServico.achado`
       nesse caso, para não sequestrar o vínculo da análise que a originou.

    `servico` é opcional: quando o chamador já tem o `ServicoCampo` carregado em
    lote (o dossiê, que monta um mapa único para evitar N+1), passa-o aqui e
    nenhuma consulta extra é feita. Sem ele, cai no acessor reverso de
    `ServicoCampo.analise_tecnica` (OneToOne — no máximo 1 consulta, cacheada
    pelo Django na própria instância do achado).
    """
    osp = getattr(achado, "osp", None)
    if osp is not None:
        return osp
    if servico is None:
        servico = getattr(achado, "balanceamento_tecnico", None)
    return servico.osp if servico is not None else None


def numero_da_osp(osp, fallback=""):
    """Formato do relatório: 'sequencial do cliente / sequencial global do BD'."""
    if osp and osp.sequencial_cliente and osp.sequencial_global:
        return f"{osp.sequencial_cliente}/{osp.sequencial_global}"
    return fallback
