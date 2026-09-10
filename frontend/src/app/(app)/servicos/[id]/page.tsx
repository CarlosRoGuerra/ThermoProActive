"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Gauge } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ServicoCampoPainel } from "@/components/servico-campo-painel";
import type { ServicoCampo } from "@/lib/types";
import { PageHeader, Spinner } from "@/components/ui";

export default function ServicoDetailPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const podeEditar = !!user?.is_interno;
  const [servico, setServico] = useState<ServicoCampo | null>(null);
  const [loading, setLoading] = useState(true);

  const carregar = useCallback(async () => {
    const dados = await api<ServicoCampo>(`/servicos/${id}/`);
    if (dados.atividade) {
      router.replace(`/servicos/atividades/${dados.atividade}?item=${dados.item}`);
      return;
    }
    setServico(dados);
  }, [id, router]);

  useEffect(() => {
    carregar().finally(() => setLoading(false));
  }, [carregar]);

  if (loading) return <Spinner />;
  if (!servico) return <p className="text-sm text-fg-muted">Serviço não encontrado.</p>;

  return (
    <div className="space-y-5">
      <PageHeader
        title={`${servico.equipamento_tag} — ${servico.tipo_display}`}
        description={`${servico.equipamento_nome} · ${servico.cliente_nome} · ${servico.data_execucao
          .split("-")
          .reverse()
          .join("/")}`}
        icon={Gauge}
      />
      <ServicoCampoPainel servico={servico} podeEditar={podeEditar} onMudou={carregar} />
    </div>
  );
}
