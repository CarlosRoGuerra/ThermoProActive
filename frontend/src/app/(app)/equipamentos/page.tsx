"use client";

import { useEffect, useState } from "react";
import { Activity, Search } from "lucide-react";
import { api } from "@/lib/api";
import type { Equipamento, Paginated } from "@/lib/types";
import { Badge, Card, CardsSkeleton, EmptyState, PageHeader } from "@/components/ui";
import { Stagger, StaggerItem } from "@/components/motion";

export default function EquipamentosPage() {
  const [equipamentos, setEquipamentos] = useState<Equipamento[]>([]);
  const [loading, setLoading] = useState(true);
  const [busca, setBusca] = useState("");

  useEffect(() => {
    api<Paginated<Equipamento>>("/equipamentos/")
      .then((d) => setEquipamentos(d.results))
      .finally(() => setLoading(false));
  }, []);

  const filtrados = equipamentos.filter(
    (e) =>
      e.tag.toLowerCase().includes(busca.toLowerCase()) ||
      e.nome.toLowerCase().includes(busca.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Activity}
        title="Equipamentos"
        description="Cadastro de máquinas e componentes (Anexo I 2.2 / 3.1)."
      />

      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-subtle" />
        <input
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="Buscar por TAG ou nome…"
          className="input pl-9"
        />
      </div>

      {loading ? (
        <CardsSkeleton count={6} />
      ) : filtrados.length === 0 ? (
        <Card>
          <EmptyState
            icon={Activity}
            title="Nenhum equipamento encontrado"
            description={busca ? "Ajuste o termo de busca." : "Cadastre equipamentos para começar a monitorá-los."}
          />
        </Card>
      ) : (
        <Stagger className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filtrados.map((e) => (
            <StaggerItem key={e.id}>
              <Card interactive className="h-full">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-base font-semibold text-fg">{e.tag}</p>
                    <p className="text-sm text-fg-muted">{e.nome}</p>
                  </div>
                  <Badge tone="accent">Classe {e.classe_iso}</Badge>
                </div>
                <dl className="mt-4 space-y-1.5 text-xs">
                  <Row k="Setor" v={e.setor_nome} />
                  <Row k="Fabricante" v={e.fabricante || "—"} />
                  <Row k="Rotação nominal" v={e.rotacao_nominal_rpm ? `${e.rotacao_nominal_rpm} RPM` : "—"} />
                  <Row k="Potência" v={e.potencia_kw ? `${e.potencia_kw} kW` : "—"} />
                </dl>
                {e.componentes.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-1.5 border-t border-border pt-3">
                    {e.componentes.map((c) => (
                      <span
                        key={c.id}
                        className="rounded-md bg-surface-muted px-2 py-0.5 text-xs text-fg-muted"
                      >
                        {c.nome}
                      </span>
                    ))}
                  </div>
                )}
              </Card>
            </StaggerItem>
          ))}
        </Stagger>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between">
      <dt className="text-fg-subtle">{k}</dt>
      <dd className="font-medium text-fg">{v}</dd>
    </div>
  );
}
