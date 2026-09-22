# Relatório corretivo de balanceamento

Continuação da [análise técnica de balanceamento](07-analise-tecnica-balanceamento.md).
Duas lacunas foram fechadas: a análise corretiva não gerava OSP, e a folha da OSP no
relatório técnico ainda descrevia uma intervenção a fazer, não uma já executada.

## Análise técnica → OSP

A OSP nasce quando a análise técnica é **salva** (`PATCH .../balanceamento/`), logo
após `tecnica.save(item=item)` e dentro da transação que já existia. Clicar em
"Analisar" continua criando apenas o `ServicoCampo` — abrir a tela não é um
diagnóstico, e uma OSP aberta ali ficaria sem conteúdo técnico.

A geração continua sendo exclusividade de `OrdemServico.gerar_de_achado`: numeração,
sequencial por cliente, sequencial global, grau de risco e a cópia dos dados do
achado. `apps.servicos.osp_corretiva.vincular_osp_da_analise` só decide quando
chamá-la e a quem amarrar o resultado, sem salvar o serviço (quem chama grava uma vez
só). A operação é idempotente: resalvar a análise, editar o detalhe ou trocar a
recomendação mantém 1 Achado, 1 OSP e 1 ServicoCampo.

Três vínculos que não se misturam:

- `ServicoCampo.analise_tecnica` → o Achado desta intervenção; é ele que vira OSP.
- `ServicoCampo.osp` → a OSP desta intervenção. Se o serviço nasceu executando uma
  OSP preditiva já aberta ("OSP de origem"), é ela que responde pelo trabalho e
  nenhuma segunda é gerada.
- `ServicoCampo.achado` → a análise de ORIGEM do fluxo preditivo. Não é sobrescrita.

`AchadoSerializer.update` segue sem gerar OSP para achados corretivos: confirmar no
escritório não é um segundo gatilho.

## Payload do relatório — uma regra de verdade

`apps.servicos.relatorio_corretivo` monta o payload a partir do que já está calculado
no banco (`BalanceamentoPonto.save`, `EconomiaEnergetica.save`, `rules.py`). Nada é
recalculado e nada é preenchido por omissão: grandeza ausente sai `null` e a
apresentação mostra o estado de ausência.

`ServicoCampoViewSet.relatorio()` e `RelatorioViewSet.dossie()` consomem a mesma
função — não há chamada HTTP interna entre views nem fórmula duplicada no front. O
contrato anterior do endpoint do serviço (`servico`, `mostrador`, `pontos`,
`economia`) continua valendo; o dossiê recebe os mesmos dados e dispensa a chave
`servico`, que repetiria planos/pontos/economia em cada folha.

`MONTADORES` despacha por tipo de serviço. O alinhamento a laser não tem montador:
enquanto suas regras técnicas não forem discutidas com o cliente, a folha permanece
no layout preditivo em vez de exibir campos inventados.

No dossiê os serviços são carregados de uma vez, indexados por `analise_tecnica_id`,
com `select_related` e `prefetch_related` — o custo em consultas não cresce com o
número de folhas (coberto por teste).

## Folha da OSP de balanceamento

O cabeçalho aprovado (OSP nº, empresa, data, analista, área, setor, TAG, equipamento,
componente, diagnóstico, observação, recomendação e Grau de Risco) é o mesmo.
Muda só a metade inferior, em `features/relatorio-inspecao/corretiva-balanceamento.tsx`:

| Preditiva | Balanceamento corretivo |
| --- | --- |
| Aceleração + Velocidade | Velocidade [mm/s] |
| Planejamento / Corretiva Prog. / Finalização | Resultado do Balanceamento |
| Linha de tendência | Mostrador de Fase — Trim Run |
| Espectro | Evolução da Vibração |
| Retorno de Informação | Economia Energética Gerada |

A foto do equipamento e o upload de evidências não mudam. Os relatórios preditivos e
de termografia seguem com o layout de sempre — a decisão é por `tipo_corretiva`.

### Trim, nunca Trial

O ângulo do relatório final é o do Trim Run. O `MostradorPolar` ganhou a propriedade
`series`: a tela de campo continua mostrando Reference/Trial/Trim, e a folha pede só
o trim. Sem Trim Run medido o mostrador diz "Trim Run ainda não informado" — não há
fallback para o Trial, que representa outra correção.

A escala do mostrador é a maior corrida **visível**. Na tela, com as três à vista,
nada muda. Na folha, com o trim sozinho, a agulha ocupa o raio inteiro: ali o que se
lê é o ângulo, e o trim, por definição o menor valor, viraria um ponto no centro.

Mostrador de fase usa `BalanceamentoPonto.trim_fase`; a correção que ficou na máquina
usa `BalanceamentoPlano.massa_final_g` e `angulo_final`. Massa e ângulo de teste
pertencem ao Trial Run e nunca aparecem como resultado. Os dois valores não são
forçados a coincidir.

### Impressão

Os gráficos são SVG/HTML gerados dos dados, não imagens: o PDF nunca discorda do
banco. O bloco redeclara os tokens do tema claro no seu escopo — `MostradorPolar` e
`AntesDepois` leem tokens que, no modo escuro, sairiam ilegíveis no papel.

A folha foi medida em Chromium com `media: print`: com 3 pontos completos, 2 planos e
a economia inteira, o conteúdo fecha em ~293mm dos 297mm do A4, sem estouro
horizontal e com as cores idênticas nos dois temas. O caso real é de 1 ou 2 pontos.

## Testes

`apps.servicos.test_analise_balanceamento` cobre a OSP: não criada ao abrir a análise;
criada e vinculada ao salvar (cliente, equipamento, achado, número e sequenciais);
não duplicada ao resalvar ou editar; não gerada quando existe OSP de origem; e
rollback completo quando a geração falha.

`apps.servicos.test_relatorio_corretivo` cobre o payload: dossiê com planos, pontos,
as três corridas, redução, zona ISO e economia numa carga só; Trial 0° com Trim 210°
resultando em 210°; `trim_fase` nulo com `trial_fase` presente sem herança; serviço
sem trim sem veredito; economia ausente como `null`; a mesma montagem nos dois
endpoints; custo em consultas estável de 1 para 4 folhas; e a regressão do relatório
preditivo (aceleração, Espectro, Tendência e Retorno de Informação intactos).
