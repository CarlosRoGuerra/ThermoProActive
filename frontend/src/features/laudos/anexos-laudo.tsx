"use client";

import { useState } from "react";
import { Trash2, Upload } from "lucide-react";
import { Alert, Button, Card, Field, Input, Textarea } from "@/components/ds";
import { api } from "@/lib/api";
import { useMutacao, useRecurso } from "@/lib/recurso";

type Anexo = { id: number; nome: string; legenda: string; mime: string; tamanho: number; data_uri: string };

export function AnexosLaudo({ laudoId, onAlterado }: { laudoId: number; onAlterado: () => void }) {
  const recurso = useRecurso<Anexo[]>(`/laudos/${laudoId}/anexos/`, "imagens do rascunho");
  const mutacao = useMutacao("imagem do laudo");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [legenda, setLegenda] = useState("");
  const [erro, setErro] = useState("");
  const [entrada, setEntrada] = useState(0);

  async function enviar() {
    if (!arquivo) { setErro("Selecione uma imagem para anexar ao rascunho."); return; }
    setErro("");
    const dados = new FormData(); dados.append("imagem", arquivo); dados.append("legenda", legenda);
    const resposta = await mutacao.executar(() => api(`/laudos/${laudoId}/anexos/`, { method: "POST", body: dados }));
    if (resposta.ok) { setArquivo(null); setLegenda(""); setEntrada(entrada + 1); recurso.recarregar(); onAlterado(); }
  }

  async function remover(id: number) {
    const resposta = await mutacao.executar(() => api(`/laudos/${laudoId}/anexos/${id}/`, { method: "DELETE" }));
    if (resposta.ok) { recurso.recarregar(); onAlterado(); }
  }

  return <Card className="no-print"><h2 className="mb-3 font-semibold text-fg">Imagens do rascunho</h2>
    <p className="mb-4 text-sm text-fg-muted">As imagens ficam vinculadas a esta versão. Na emissão, o documento preserva as evidências utilizadas.</p>
    <div className="space-y-4">
      {recurso.falha && <Alert tone="warning" title="Imagens indisponíveis">{recurso.falha.descricao}<Button variant="link" onClick={recurso.recarregar}>Tentar novamente</Button></Alert>}
      {mutacao.falha && <Alert tone="danger" title={mutacao.falha.titulo}>{mutacao.falha.descricao}</Alert>}
      <Field label="Imagem" obrigatorio erro={erro} hint="Imagem estática. O servidor verifica o formato e os limites de tamanho configurados.">
        <Input key={entrada} type="file" accept="image/png,image/jpeg,image/webp,image/gif,image/tiff,image/bmp" onChange={(e) => { setArquivo(e.target.files?.[0] ?? null); setErro(""); }} />
      </Field>
      <Field label="Legenda da imagem"><Textarea value={legenda} maxLength={1000} onChange={(e) => setLegenda(e.target.value)} /></Field>
      <Button icon={Upload} onClick={enviar} loading={mutacao.enviando}>Anexar imagem</Button>
      {recurso.dados && recurso.dados.length === 0 && <p className="text-sm text-fg-muted">Nenhuma imagem anexada a este rascunho.</p>}
      <ul className="grid gap-4 sm:grid-cols-2">{recurso.dados?.map((a) => <li key={a.id} className="min-w-0 border-t border-border pt-3">
        {/^data:image\//i.test(a.data_uri) && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={a.data_uri} alt={a.legenda || a.nome} className="mb-2 max-h-48 w-full object-contain" />
        )}
        <p className="break-words text-sm text-fg">{a.legenda || a.nome}</p>
        <Button variant="ghost" size="sm" icon={Trash2} disabled={mutacao.enviando} onClick={() => remover(a.id)} aria-label={`Remover imagem ${a.legenda || a.nome}`}>Remover do rascunho</Button>
      </li>)}</ul>
    </div>
  </Card>;
}
