# Análise técnica de balanceamento na atividade corretiva

## Operação

Na atividade de Balanceamento, selecione a condição do equipamento e clique em
Analisar. A tela usa o serviço já vinculado ao item da rota e apresenta condição,
tipo de componente, componente (texto), detalhe, anomalia e recomendação.
Salvar análise grava os dados no mesmo item; voltar e continuar reabre o registro.

Os blocos de planos e pontos reutilizam a folha existente: massas e ângulos de
teste/final, Reference Run, Trial Run e Trim Run, amplitude, fase, resultado e
redução. Cada bloco mantém seus controles de salvar. Nenhuma regra nova de Classe
ISO, campo de motor, OCR/IA ou cadastro dinâmico de equipamento foi introduzido.

## Modelos e cadastros

- `Carregamento` e `ItemInspecao`: atividade, rota e equipamento, como na fase anterior.
- `ServicoCampo`: cabeçalho e rotação; `analise_tecnica` aponta para um `Achado` do
  mesmo item. O campo `achado` continua sendo a análise de origem da intervenção.
- `Achado`: condição, tipo de componente, `componente_texto`, detalhe, anomalia,
  recomendação e complementos. São campos existentes, também usados pelo relatório.
- `BalanceamentoPlano` e `BalanceamentoPonto`: massas, corridas e resultados existentes.
- `TipoComponente`, `TipoAnomalia` e `TipoRecomendacao`: vínculo explícito com a
  tecnologia da atividade. Catálogos sem vínculo não são universais neste fluxo.
- `TipoRecomendacao.anomalias`: nova associação que permite definir recomendações
  compatíveis em Dados de sistema → Tipos de recomendação. A curadoria conserva
  as permissões existentes. Não são criadas associações por nome ou automaticamente.

O campo Componente permanece o texto já utilizado pelo domínio `Achado`; não é
criado outro cadastro nem novos campos no modelo de equipamentos.

## API

Sob `/api/atividades-corretivas/{atividade}/itens/{item}/`:

- `GET balanceamento/`: serviço e análise técnica, ou `tecnica: null` antes do primeiro salvamento.
- `PATCH balanceamento/`: recebe `tecnica` com os campos do Achado e, opcionalmente,
  `rotacao_hz`; valida e salva tudo em transação, sem abrir nova atividade.
- `GET balanceamento/catalogos/`: condições, tipos de componente e anomalias válidos.
- `GET balanceamento/catalogos/?anomalia={id}`: inclui apenas recomendações válidas
  para a tecnologia da atividade **e** a anomalia solicitada.

Os endpoints existentes `/api/balanceamento-planos/` e `/api/balanceamento-pontos/`
continuam sendo usados. Validam tipo de serviço, atividade aberta, vínculo do plano
e imutabilidade do serviço em uma edição. Os cálculos existentes permanecem iguais.

## Validação e permissões

Condição e os três seletores de catálogo são exigidos ao salvar a análise técnica.
Cada opção precisa estar ativa. Componente, anomalia e recomendação precisam estar
vinculados explicitamente à tecnologia real da atividade, determinada pela URL.
A recomendação também precisa estar vinculada à anomalia. Em edição parcial, o
backend revalida a combinação final, incluindo os valores que não foram enviados.

O item é buscado dentro da atividade; a análise técnica é obtida pelo serviço desse
item. O cliente só consulta suas próprias atividades. Internos editam atividades
abertas; exclusão de planos/pontos continua sujeita ao nível de acesso. Os endpoints
genéricos preditivos de Achado não permitem acessar/alterar os achados corretivos;
o vínculo `analise_tecnica` também é somente leitura no serializer geral de serviço.

## Frontend e testes

`analise-balanceamento.tsx` implementa a tela contextual; `balanceamento-medicoes.tsx`
compartilha Planos/Pontos entre a tela antiga e a atividade por rota. A página da
atividade escolhe a tela pelo tipo persistido; a página de cadastros permite manter
as associações recomendação/anomalia.

`test_analise_balanceamento.py` cobre catálogos filtrados, combinações incompatíveis,
edição parcial, persistência, permissões, isolamento, tentativas pelos endpoints
genéricos, medições/cálculos, plano de outro serviço, atividade fechada e rollback.
Migrations aditivas: `cadastros.0023` e `servicos.0005`; registros antigos recebem
vínculo técnico nulo e os catálogos não são reclassificados.
