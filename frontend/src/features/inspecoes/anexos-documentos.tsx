"use client";

/**
 * Anexos de documento (Anexo I 2.3.1.3): laudo de laboratório, planilha, DOCX.
 *
 * Vinculado à inspeção (relatório), ao equipamento ou aos dois. O servidor é a
 * fonte de verdade: confere o CONTEÚDO do arquivo, o tamanho e o cliente de cada
 * vínculo. Aqui só se filtra o tipo e o tamanho para dar retorno rápido.
 * Cliente vê a lista e baixa apenas o que o técnico marcou como visível.
 */

import { useCallback, useEffect, useState } from "react";
import { Download, Paperclip, Trash2, Upload } from "lucide-react";
import { api, ApiError, downloadFile } from "@/lib/api";
import type { Paginated } from "@/lib/types";
import { Badge, Button, Card, Field, Input, Select } from "@/components/ds";

export interface AnexoDocumento {
  id: number;
  categoria: string;
  categoria_display: string;
  arquivo: string;
  nome_original: string;
  tamanho_bytes: number;
  descricao: string;
  visivel_cliente: boolean;
  criado_em: string;
}

const CATEGORIAS = [
  { valor: "LAUDO_LABORATORIO", texto: "Laudo de laboratório" },
  { valor: "PLANILHA", texto: "Planilha / dados" },
  { valor: "RELATORIO", texto: "Relatório" },
  { valor: "DOCUMENTO", texto: "Documento" },
];

/** Espelha `coletas.anexos.TIPOS_DOCUMENTO` e o limite padrão (o servidor é quem decide). */
const EXTENSOES = ".pdf,.xlsx,.docx,.csv";
const LIMITE_MB = 20;

/** `arquivo` vem como URL de mídia; o download é autenticado pelo caminho `/media/...`. */
function caminhoDaMidia(url: string): string | null {
  const m = url.match(/\/media\/(.+)$/);
  return m ? `/media/${m[1]}` : null;
}

function tamanhoLegivel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function mensagem(erro: unknown, padrao: string): string {
  if (erro instanceof ApiError) return erro.message || padrao;
  return padrao;
}

/** Corpo de erro de validação por campo (`{arquivo: ["..."]}`), seja objeto ou texto JSON. */
function detalhesDoErro(dados: unknown): Record<string, string[] | string> | null {
  if (dados && typeof dados === "object") return dados as Record<string, string[] | string>;
  if (typeof dados === "string") {
    try {
      const obj = JSON.parse(dados);
      return obj && typeof obj === "object" ? (obj as Record<string, string[] | string>) : null;
    } catch {
      return null;
    }
  }
  return null;
}

interface Props {
  /** Vínculos: pelo menos um. Todos devem ser do mesmo cliente (o servidor confere). */
  cliente: number;
  relatorio?: number | null;
  inspecao?: number | null;
  equipamento?: number | null;
  titulo?: string;
  /** Interno envia, marca visibilidade e remove. Cliente só lista e baixa. */
  podeEditar: boolean;
}

export function AnexosDocumentos({
  cliente, relatorio, inspecao, equipamento, titulo = "Documentos anexados", podeEditar,
}: Props) {
  const [anexos, setAnexos] = useState<AnexoDocumento[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [categoria, setCategoria] = useState("DOCUMENTO");
  const [descricao, setDescricao] = useState("");
  const [visivel, setVisivel] = useState(false);
  const [enviando, setEnviando] = useState(false);

  const filtro = relatorio
    ? `relatorio=${relatorio}`
    : inspecao
      ? `inspecao=${inspecao}`
      : equipamento
        ? `equipamento=${equipamento}`
        : "";

  const carregar = useCallback(async () => {
    if (!filtro) {
      setAnexos([]);
      return;
    }
    try {
      const r = await api<Paginated<AnexoDocumento>>(`/anexos-documentos/?${filtro}&page_size=200`);
      setAnexos(r.results);
    } catch (e) {
      setErro(mensagem(e, "Não foi possível carregar os documentos."));
      setAnexos([]);
    }
  }, [filtro]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  function escolherArquivo(f: File | null) {
    setErro(null);
    if (!f) return setArquivo(null);
    const ext = f.name.slice(f.name.lastIndexOf(".")).toLowerCase();
    if (!EXTENSOES.split(",").includes(ext)) {
      setErro("Tipo não aceito. Envie PDF, XLSX, DOCX ou CSV.");
      return setArquivo(null);
    }
    if (f.size > LIMITE_MB * 1024 * 1024) {
      setErro(`O arquivo excede ${LIMITE_MB} MB.`);
      return setArquivo(null);
    }
    setArquivo(f);
  }

  async function enviar() {
    if (!arquivo) return;
    setEnviando(true);
    setErro(null);
    try {
      const corpo = new FormData();
      corpo.append("cliente", String(cliente));
      if (relatorio) corpo.append("relatorio", String(relatorio));
      if (inspecao) corpo.append("inspecao", String(inspecao));
      if (equipamento) corpo.append("equipamento", String(equipamento));
      corpo.append("categoria", categoria);
      corpo.append("descricao", descricao);
      corpo.append("visivel_cliente", visivel ? "true" : "false");
      corpo.append("arquivo", arquivo);
      await api("/anexos-documentos/", { method: "POST", body: corpo });
      setArquivo(null);
      setDescricao("");
      setVisivel(false);
      await carregar();
    } catch (e) {
      // Erro de conteúdo vem por campo ({arquivo: ["..."]}); mostra a primeira mensagem.
      const dados = e instanceof ApiError ? detalhesDoErro(e.data) : null;
      if (dados) {
        const primeiro = Object.values(dados)[0];
        setErro(Array.isArray(primeiro) ? String(primeiro[0]) : String(primeiro));
        return;
      }
      setErro(mensagem(e, "Não foi possível enviar o arquivo."));
    } finally {
      setEnviando(false);
    }
  }

  async function baixar(a: AnexoDocumento) {
    const caminho = caminhoDaMidia(a.arquivo);
    if (!caminho) return setErro("Arquivo indisponível.");
    try {
      await downloadFile(caminho, a.nome_original);
    } catch (e) {
      setErro(mensagem(e, "Não foi possível baixar o arquivo."));
    }
  }

  async function alternarVisivel(a: AnexoDocumento) {
    try {
      await api(`/anexos-documentos/${a.id}/`, { method: "PATCH", body: { visivel_cliente: !a.visivel_cliente } });
      await carregar();
    } catch (e) {
      setErro(mensagem(e, "Não foi possível alterar a visibilidade."));
    }
  }

  async function remover(a: AnexoDocumento) {
    if (!window.confirm(`Remover o documento "${a.nome_original}"? O arquivo é apagado.`)) return;
    try {
      await api(`/anexos-documentos/${a.id}/`, { method: "DELETE" });
      await carregar();
    } catch (e) {
      setErro(mensagem(e, "Não foi possível remover o documento."));
    }
  }

  return (
    <Card as="section" className="space-y-3">
      <h2 className="flex items-center gap-2 font-semibold text-fg">
        <Paperclip className="h-4 w-4" aria-hidden /> {titulo}
      </h2>
      {erro && <p role="alert" className="text-sm text-danger-fg">{erro}</p>}

      {anexos === null ? (
        <p className="text-sm text-fg-muted">Carregando…</p>
      ) : anexos.length === 0 ? (
        <p className="text-sm text-fg-muted">Nenhum documento anexado.</p>
      ) : (
        <ul className="divide-y divide-border">
          {anexos.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center gap-2 py-2">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-fg">{a.nome_original}</p>
                <p className="text-xs text-fg-muted">
                  {a.categoria_display} · {tamanhoLegivel(a.tamanho_bytes)}
                  {a.descricao ? ` · ${a.descricao}` : ""}
                </p>
              </div>
              {podeEditar && (
                <Badge tone={a.visivel_cliente ? "success" : "neutral"}>
                  {a.visivel_cliente ? "Visível ao cliente" : "Interno"}
                </Badge>
              )}
              <Button variant="ghost" icon={Download} onClick={() => baixar(a)}>
                Baixar
              </Button>
              {podeEditar && (
                <>
                  <Button variant="ghost" onClick={() => alternarVisivel(a)}>
                    {a.visivel_cliente ? "Ocultar do cliente" : "Mostrar ao cliente"}
                  </Button>
                  <Button variant="ghost" icon={Trash2} onClick={() => remover(a)}>
                    Remover
                  </Button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {podeEditar && filtro && (
        <div className="grid gap-3 border-t border-border pt-3 sm:grid-cols-2">
          <Field label="Arquivo (PDF, XLSX, DOCX ou CSV)">
            <Input
              type="file"
              accept={EXTENSOES}
              onChange={(e) => escolherArquivo(e.target.files?.[0] ?? null)}
            />
          </Field>
          <Field label="Categoria">
            <Select value={categoria} onChange={(e) => setCategoria(e.target.value)}>
              {CATEGORIAS.map((c) => (
                <option key={c.valor} value={c.valor}>{c.texto}</option>
              ))}
            </Select>
          </Field>
          <Field label="Descrição">
            <Input value={descricao} maxLength={200} onChange={(e) => setDescricao(e.target.value)} />
          </Field>
          <label className="flex items-center gap-2 text-sm text-fg">
            <input type="checkbox" checked={visivel} onChange={(e) => setVisivel(e.target.checked)} />
            Visível para o cliente
          </label>
          <div className="sm:col-span-2">
            <Button icon={Upload} onClick={enviar} loading={enviando} disabled={!arquivo}>
              Enviar documento
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
