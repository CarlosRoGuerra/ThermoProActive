import { api } from "@/lib/api";

export type ContextoAuth = "portal" | "admin";

export function solicitarRecuperacao(contexto: ContextoAuth, email: string) {
  return api<{ detail: string }>(`/auth/${contexto}/esqueci-senha/`, {
    method: "POST",
    body: { email },
    retry: false,
  });
}

export function redefinirSenha(token: string, novaSenha: string) {
  return api<{ detail: string; contexto: ContextoAuth }>("/auth/redefinir-senha/", {
    method: "POST",
    body: { token, nova_senha: novaSenha },
    retry: false,
  });
}

export function verificarEmail(token: string) {
  return api<{ detail: string }>("/auth/verificar-email/", {
    method: "POST", body: { token }, retry: false,
  });
}

export function reenviarVerificacao(email: string) {
  return api<{ detail: string }>("/auth/verificar-email/reenviar/", {
    method: "POST", body: { email }, retry: false,
  });
}

export function consultarConvite(token: string) {
  return api<{ valid: boolean; nome: string; email: string; tipo: ContextoAuth }>(
    `/auth/convites/${encodeURIComponent(token)}/`, { retry: false }
  );
}

export function aceitarConvite(token: string, senha: string, aceitouTermos: boolean) {
  return api<{ detail: string; contexto: ContextoAuth }>(
    `/auth/convites/${encodeURIComponent(token)}/`,
    { method: "POST", body: { senha, aceitou_termos: aceitouTermos }, retry: false }
  );
}

export type PedidoAcesso = {
  nome: string;
  email: string;
  telefone: string;
  razao_social: string;
  nome_fantasia: string;
  cnpj: string;
  segmento: string;
  telefone_empresa: string;
  email_empresa: string;
  quantidade_equipamentos: number | null;
  cargo: string;
  aceitou_termos: boolean;
  aceita_marketing: boolean;
};

export function enviarSolicitacaoAcesso(dados: PedidoAcesso) {
  return api<{ detail: string }>("/auth/solicitacoes-acesso/", {
    method: "POST",
    body: dados,
    retry: false,
  });
}

export type ResumoSeguranca = {
  mfa_ativo: boolean;
  mfa_obrigatorio: boolean;
  email_verificado: boolean;
  senha_alterada_em: string | null;
  sessoes_ativas: number;
};

export type Sessao = {
  id: string;
  atual: boolean;
  dispositivo: string;
  ultimo_uso_em: string;
  criado_em: string;
};

export type Evento = { evento: string; sucesso: boolean; criado_em: string };

export function obterSeguranca() {
  return Promise.all([
    api<ResumoSeguranca>("/auth/seguranca/"),
    api<Sessao[]>("/auth/seguranca/sessoes/"),
    api<Evento[]>("/auth/seguranca/eventos/"),
  ]);
}

export function alterarSenha(senhaAtual: string, novaSenha: string) {
  return api<{ detail: string }>("/auth/seguranca/alterar-senha/", {
    method: "POST", body: { senha_atual: senhaAtual, nova_senha: novaSenha },
  });
}

export function encerrarOutrasSessoes() {
  return api<void>("/auth/seguranca/sessoes/", { method: "DELETE" });
}

export function iniciarMfa() {
  return api<{ secret: string; otpauth_uri: string }>("/auth/mfa/setup/", { method: "POST" });
}

export function confirmarMfa(codigo: string) {
  return api<{ detail: string; recovery_codes: string[] }>("/auth/mfa/confirm/", {
    method: "POST", body: { codigo },
  });
}
