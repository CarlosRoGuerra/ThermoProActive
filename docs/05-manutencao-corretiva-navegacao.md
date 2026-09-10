# Manutenção corretiva — nomenclatura e navegação

Registro da fase de nomenclatura. O fluxo de abertura foi posteriormente evoluído
em [Manutenção corretiva por rota](06-manutencao-corretiva-por-rota.md).

O agrupador funcional é **Manutenção corretiva**, implementado no módulo existente
`apps.servicos` e nas páginas `/servicos`, `/servicos/novo` e `/servicos/[id]`.
O menu interno e o portal do cliente compartilham as entradas:

- Balanceamento;
- Alinhamento a laser, com subdivisões previstas entre polias e entre eixos;
- Outros trabalhos corretivos (outros serviços corretivos), previsto.

Os submenus apontam para seções da página existente. As subdivisões futuras são
apresentadas como “em breve”, sem novos formulários nem classificação automática
dos registros antigos. A listagem continua mostrando todos os serviços do cliente.

## Contratos preservados

`ServicoCampo`, seus serializers e tipos TypeScript continuam com seus nomes
técnicos. `TipoServico` mantém `BALANCEAMENTO` e `ALINHAMENTO`; ainda não existe
distinção persistida entre polias e eixos. `TipoAnalise.CORRETIVA` em `coletas`
continua independente e inalterado. A API `/api/servicos/`, os endpoints de planos,
pontos e economia, os vínculos com OSP/achado/relatório e a permissão
`InternoEditaClienteVisualiza` permanecem compatíveis.

A migration `0003_manutencao_corretiva_labels` altera somente metadados de exibição
do admin (`AlterModelOptions`), sem alterar tabelas, campos ou registros. O nome
antigo na migration inicial é histórico e deve permanecer. O comando local de seed
de balanceamento preexistente não precisa de alterações para continuar funcionando.

Esta fase não amplia cálculos, coleta/análise, formulários técnicos ou regras de
negócio. O discovery técnico permanece em
[04-DISCOVERY-balanceamento-e-economia.md](04-DISCOVERY-balanceamento-e-economia.md).
