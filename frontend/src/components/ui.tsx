/**
 * COMPATIBILIDADE DOS DOCUMENTOS — não use em tela nova.
 *
 * Os arquivos do Relatório Técnico e do dossiê de inspeção estão no conteúdo
 * APROVADO pelo cliente e não devem ser reescritos para acompanhar refatoração
 * de interface. Eles importam daqui; este módulo apenas reexporta o Design
 * System (`@/components/ds`), que mantém os mesmos nomes e a mesma API.
 *
 * Quem consome:
 *   src/app/(admin)/laudos/[id]/relatorio/page.tsx   (Relatório Técnico)
 *   src/features/relatorio-inspecao/dossie.tsx        (dossiê de inspeção)
 *
 * Em tela nova, importe de `@/components/ds`.
 */
export {
  cn,
  Button,
  Card,
  Field,
  Input,
  Select,
  Textarea,
  Spinner,
  Badge,
  Table,
  THead,
  TH,
  TBody,
  TR,
  TD,
  EmptyState,
  PageHeader,
} from "./ds";
