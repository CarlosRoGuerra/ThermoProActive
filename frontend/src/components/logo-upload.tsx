"use client";

import { useRef, useState } from "react";
import { ImagePlus, Trash2, Upload } from "lucide-react";
import { cn } from "./ui";

const TAMANHO_MAX_MB = 20; // alinhado ao limite do backend (DATA_UPLOAD_MAX_MEMORY_SIZE)

/**
 * Upload de logomarca com prévia quadrada (250×250).
 * Reporta o arquivo escolhido ao pai; a prévia inicial pode ser a URL já salva.
 */
export function LogoUpload({
  urlAtual,
  onArquivo,
  label = "Logomarca",
  ajuda = "Logomarca horizontal, PNG com fundo transparente, recortada rente (ex.: ~2000px de largura). Sai no cabeçalho e nas capas do relatório.",
}: {
  urlAtual?: string | null;
  onArquivo: (arquivo: File | null) => void;
  label?: string;
  ajuda?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(urlAtual ?? null);
  const [removida, setRemovida] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  function escolher(arquivo: File | null) {
    setErro(null);
    if (!arquivo) return;
    if (!arquivo.type.startsWith("image/")) {
      setErro("Selecione um arquivo de imagem (PNG, JPG…).");
      return;
    }
    if (arquivo.size > TAMANHO_MAX_MB * 1024 * 1024) {
      setErro(`Imagem muito grande (máx. ${TAMANHO_MAX_MB} MB).`);
      return;
    }
    setPreview(URL.createObjectURL(arquivo));
    setRemovida(false);
    onArquivo(arquivo);
  }

  function remover() {
    setPreview(null);
    setRemovida(true);
    onArquivo(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div>
      <label className="label">{label}</label>
      <div className="flex items-start gap-4">
        {/* Prévia / área de soltar */}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            escolher(e.dataTransfer.files?.[0] ?? null);
          }}
          className={cn(
            "relative flex h-[90px] w-[200px] shrink-0 items-center justify-center overflow-hidden rounded-xl border border-dashed border-border-strong bg-surface-muted transition-colors hover:border-accent",
          )}
          aria-label="Selecionar logomarca"
        >
          {preview ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={preview} alt="Prévia da logomarca" className="h-full w-full object-contain" />
          ) : (
            <span className="flex flex-col items-center gap-1 text-fg-subtle">
              <ImagePlus className="h-6 w-6" />
              <span className="text-[10px]">PNG</span>
            </span>
          )}
        </button>

        <div className="flex flex-col gap-2 pt-1">
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-medium text-fg-muted transition-colors hover:bg-surface-muted hover:text-fg"
            >
              <Upload className="h-3.5 w-3.5" /> {preview ? "Trocar" : "Enviar imagem"}
            </button>
            {preview && (
              <button
                type="button"
                onClick={remover}
                className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-danger-fg transition-colors hover:bg-danger-subtle"
              >
                <Trash2 className="h-3.5 w-3.5" /> Remover
              </button>
            )}
          </div>
          <p className="max-w-[220px] text-xs text-fg-subtle">{ajuda}</p>
          {erro && <p className="text-xs text-danger-fg">{erro}</p>}
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => escolher(e.target.files?.[0] ?? null)}
      />
      {/* Sinaliza ao pai a intenção de remover a logo já salva. */}
      {removida && <input type="hidden" data-logo-removida="true" />}
    </div>
  );
}
