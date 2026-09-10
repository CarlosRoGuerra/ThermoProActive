# Manutenção corretiva por rota

A tela específica de Balanceamento foi evoluída na
[fase de análise técnica](07-analise-tecnica-balanceamento.md).

## Operação

1. Ative o cliente no seletor existente.
2. Acesse Manutenção corretiva → Nova atividade / Carregar rota.
3. Selecione tecnologia, rota e instrumento compatível. O analista é o usuário autenticado.
4. Informe a data real de término/ensaio, até a data atual.
5. Carregue a rota. O relatório recebe um novo número pelo mecanismo existente.
6. Selecione a condição de cada equipamento e clique em Analisar.
7. Continue a análise pela mesma linha. Nesta fase, a tela exibe o contexto e permite
   salvar observações; o formulário técnico será implementado na próxima fase.

Em Dados de sistema → Tecnologias de análise, o responsável com permissão de
curadoria configura “Análise de manutenção corretiva”: Balanceamento ou Alinhamento
a laser. O campo vazio mantém a tecnologia fora das opções corretivas. Não há
classificação automática por nome ou sigla, nem criação automática de catálogos,
rotas ou instrumentos. O vínculo instrumento/tecnologia usa o cadastro existente.

## Reuso e rastreabilidade

Não há uma nova tabela de atividade ou cadastro paralelo de rotas. A atividade é
um `Carregamento` com `tipo_corretiva` preenchido a partir da tecnologia. A criação
reutiliza `CarregamentoSerializer.create`, `Relatorio.proximo_numero` e a cópia dos
equipamentos para `ItemInspecao`. Os itens são um retrato da rota no carregamento;
alterações posteriores na composição da rota não removem os equipamentos carregados.

`ServicoCampo.item` é um vínculo opcional e único com o item. O botão Analisar usa
uma transação, bloqueia a linha do item e cria ou reutiliza o serviço associado.
Cliente, equipamento, tipo, relatório, instrumento, analista e data são herdados da
atividade. A condição permanece no item; observações ficam no serviço existente.
O tipo é registrado no carregamento para que alterações no catálogo não
reclassifiquem atividades anteriores. O estado “Análise iniciada” não afirma que
o ensaio técnico foi concluído.

## API e compatibilidade

- `GET/POST /api/atividades-corretivas/`: consultar ou carregar uma rota.
- `GET /api/atividades-corretivas/{id}/`: cabeçalho e todos os equipamentos.
- `PATCH /api/atividades-corretivas/{id}/itens/{item}/condicao/`: registrar condição.
- `POST /api/atividades-corretivas/{id}/itens/{item}/analise/`: iniciar/retomar.
- `GET/PATCH` no mesmo caminho: consultar/salvar observações da análise existente.

O escopo do item é sempre a atividade da URL. Internos escrevem; clientes apenas
consultam suas próprias atividades, conforme `InternoEditaClienteVisualiza`.
Não há exclusão ou troca de rota desta atividade. Os endpoints preditivos de
carregamentos e itens mantêm os registros com `tipo_corretiva` vazio. A criação de
itens/achados preditivos não aceita uma atividade corretiva como origem.

Serviços anteriores continuam com `item=NULL`, acessíveis pela API e tela antigas.
Serviços da nova atividade abrem a tela vinculada à rota, inclusive ao acessar a
URL antiga de detalhe. Não há migração automática de serviços antigos para rotas.

## Migrations e validação

Aplicar `python manage.py migrate`: os novos campos são aditivos, com valor vazio
ou nulo para os registros existentes. Nenhum equipamento ou análise é removido.

Os testes em `apps.servicos.test_atividades` cobrem cinco equipamentos da rota,
rastreabilidade, retomada sem duplicação, isolamento por atividade/cliente,
compatibilidade de tecnologia/instrumento, datas, rollback e o fluxo preditivo
até a transferência. A validação local usa SQLite; concorrência real em PostgreSQL
deve ser exercitada no ambiente de integração.
