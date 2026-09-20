/**
 * Design System ThermoProActive — ponto único de importação.
 *
 *   import { Button, DataTable, PageHeader } from "@/components/ds";
 *
 * Nada de estilo solto nas telas: se um padrão visual aparece em duas páginas,
 * ele vira componente aqui. Tokens em `src/app/globals.css` + `tailwind.config.ts`.
 */

export { cn, TOM_SUAVE, TOM_SOLIDO, TOM_TEXTO, TOM_BORDA, type Tom } from "./utils";

/* Primitivos de ação */
export {
  Button,
  IconButton,
  ButtonGroup,
  type ButtonProps,
  type ButtonVariant,
  type ButtonSize,
  type IconButtonProps,
} from "./button";

/* Formulário */
export {
  Field,
  Input,
  Textarea,
  Select,
  SearchInput,
  Checkbox,
  Switch,
  RadioGroup,
  FormSection,
  FormGrid,
  FormActions,
  type InputProps,
} from "./field";

/* Selos e semântica de estado */
export {
  Badge,
  EstadoBadge,
  EstadoPonto,
  LegendaEstados,
  GRAUS,
  ORDEM_GRAVIDADE,
  pesoGravidade,
  grauDe,
  CriticidadeBadge,
  StatusBadge,
  PriorityBadge,
  ClasseAtivoBadge,
  SemDado,
  DicaSelo,
  type GrauMonitoramento,
} from "./badge";

/* Superfícies */
export {
  Card,
  CardHeader,
  CardSection,
  MetricCard,
  StatCard,
  DescriptionList,
} from "./card";

/* Estrutura de página */
export {
  PageHeader,
  SectionHeader,
  Breadcrumb,
  Toolbar,
  PageBody,
  MetricGrid,
  SplitLayout,
  type Trilha,
} from "./layout";

/* Estados do sistema */
export {
  Alert,
  Spinner,
  Skeleton,
  LoadingState,
  TableSkeleton,
  CardsSkeleton,
  EmptyState,
  ErrorState,
  ErrorCard,
  PermissionDenied,
  OfflineBanner,
  Resultado,
} from "./feedback";

/* Sobreposições */
export {
  Modal,
  Drawer,
  ConfirmDialog,
  useConfirmacao,
  DropdownMenu,
  Tooltip,
  type ItemMenu,
  type ModalTamanho,
} from "./overlay";

/* Avisos efêmeros */
export { ToastProvider, useToast } from "./toast";

/* Navegação interna de conteúdo */
export { Tabs, TabsLink, SegmentedControl, type Aba } from "./tabs";

/* Tabelas */
export {
  Table,
  THead,
  TH,
  TBody,
  TR,
  TD,
  Pagination,
  DataTable,
  type Coluna,
} from "./table";

/* Marca */
export { Logo, Simbolo } from "./brand";

/* Complementos */
export { Avatar, ThemeToggle, BarMeter, ProgressBar, Timeline, TimelineItem } from "./misc";
