import { ApiError } from "./api";

/**
 * Tradução de falha técnica → frase que o usuário entende.
 *
 * Regra do produto: o usuário NUNCA lê "Erro 500", "resource", "payload" nem
 * stack trace. Ele lê o que aconteceu e o que fazer. O detalhe técnico vai para
 * o console (ver `registrarFalha`), onde o suporte consegue achar.
 */

export type Falha = {
  /** Título curto: o que aconteceu. */
  titulo: string;
  /** Uma frase: o que o usuário pode fazer. */
  descricao: string;
  /** Classifica o tratamento da tela (estado de erro vs. permissão vs. sessão). */
  tipo: "permissao" | "sessao" | "nao-encontrado" | "validacao" | "conexao" | "servidor";
  /** `true` quando repetir a mesma ação pode funcionar. */
  podeTentarNovamente: boolean;
};

const CONEXAO: Falha = {
  titulo: "Sem conexão com o servidor",
  descricao:
    "Verifique sua internet. Os dados aparecem assim que a conexão voltar — nada do que você digitou foi perdido.",
  tipo: "conexao",
  podeTentarNovamente: true,
};

/** Extrai a mensagem de validação que o DRF devolve por campo, se houver. */
function mensagemDeValidacao(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const registro = data as Record<string, unknown>;
  if (typeof registro.detail === "string") return registro.detail;
  const partes: string[] = [];
  for (const [campo, valor] of Object.entries(registro)) {
    const textos = Array.isArray(valor) ? valor.map(String) : [String(valor)];
    // `non_field_errors` é jargão do DRF: some com o nome, mantém a mensagem.
    const rotulo = campo === "non_field_errors" || campo === "detail" ? "" : `${campo}: `;
    partes.push(`${rotulo}${textos.join(" ")}`);
  }
  return partes.length ? partes.join(" · ") : null;
}

/** Converte qualquer erro capturado numa Falha apresentável. */
export function interpretarFalha(e: unknown): Falha {
  if (e instanceof ApiError) {
    if (e.status === 401)
      return {
        titulo: "Sua sessão expirou",
        descricao: "Entre novamente para continuar de onde parou.",
        tipo: "sessao",
        podeTentarNovamente: false,
      };
    if (e.status === 403)
      return {
        titulo: "Você não tem acesso a esta informação",
        descricao:
          "Seu perfil não inclui esta área. Fale com o administrador do sistema se precisar dela.",
        tipo: "permissao",
        podeTentarNovamente: false,
      };
    if (e.status === 404)
      return {
        titulo: "Registro não encontrado",
        descricao: "Ele pode ter sido removido ou o endereço está incorreto.",
        tipo: "nao-encontrado",
        podeTentarNovamente: false,
      };
    if (e.status === 400 || e.status === 409 || e.status === 422)
      return {
        titulo: "Confira os dados informados",
        descricao: mensagemDeValidacao(e.data) ?? "Algum campo está incompleto ou fora do formato esperado.",
        tipo: "validacao",
        podeTentarNovamente: false,
      };
    if (e.status === 0) return CONEXAO;
    return {
      titulo: "Não foi possível completar a operação",
      descricao: "O servidor não respondeu como esperado. Tente novamente em alguns instantes.",
      tipo: "servidor",
      podeTentarNovamente: true,
    };
  }

  // `fetch` rejeita com TypeError quando não há rede / servidor fora do ar.
  if (e instanceof TypeError) return CONEXAO;

  return {
    titulo: "Algo não funcionou como esperado",
    descricao: "Tente novamente. Se continuar, avise o suporte com o horário em que aconteceu.",
    tipo: "servidor",
    podeTentarNovamente: true,
  };
}

/** Frase única, para toast e mensagem inline. */
export function mensagemDeErro(e: unknown, padrao?: string): string {
  const falha = interpretarFalha(e);
  if (falha.tipo === "validacao") return falha.descricao;
  return padrao && falha.tipo === "servidor" ? padrao : `${falha.titulo}. ${falha.descricao}`;
}

/**
 * Manda o detalhe técnico para o console (com contexto) sem mostrá-lo na tela.
 * Ponto único caso o projeto passe a enviar erros para um serviço de telemetria.
 */
export function registrarFalha(contexto: string, e: unknown) {
  if (process.env.NODE_ENV !== "production") {
    console.error(`[Pred Ativos] ${contexto}`, e);
  }
}
