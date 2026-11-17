/* Área administrativa de IA — espelho de `backend/apps/ia` (models.py e serializers.py).
   A chave de API só existe como campo de ESCRITA: nenhuma resposta a devolve. */

export type ProvedorIA = "ANTHROPIC" | "OPENAI" | "GOOGLE" | "OUTRO";

export const PROVEDORES: { valor: ProvedorIA; rotulo: string }[] = [
  { valor: "ANTHROPIC", rotulo: "Anthropic (Claude)" },
  { valor: "OPENAI", rotulo: "OpenAI (GPT)" },
  { valor: "GOOGLE", rotulo: "Google (Gemini)" },
  { valor: "OUTRO", rotulo: "Outro provedor (endereço próprio)" },
];

export type ChaveIA = {
  id: number;
  provedor: ProvedorIA;
  provedor_display: string;
  rotulo: string;
  /** "••••" + os 4 últimos caracteres. */
  chave_mascarada: string;
  modelo_padrao: string;
  url_base: string;
  /** Falso quando a chave de cifra do servidor mudou: é preciso cadastrar a chave de novo. */
  legivel: boolean;
  /** Recursos habilitados que usam esta chave. */
  em_uso: string[];
  criado_em: string;
  atualizado_em: string;
};

export type AtivacaoIA = {
  recurso: string;
  recurso_display: string;
  descricao: string;
  /** Falso = a função ainda não existe no sistema; a ativação fica gravada e nada é enviado. */
  implementado: boolean;
  habilitado: boolean;
  credencial: number | null;
  credencial_rotulo: string;
  modelo: string;
  modelo_efetivo: string;
  atualizado_em: string | null;
};
