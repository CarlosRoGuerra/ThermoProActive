"use client";

import { useEffect, useState } from "react";
import { api } from "./api";
import type { Cliente, Paginated } from "./types";
import type { Opcao } from "@/components/combobox";

export type Area = {
  id: number;
  cliente: number;
  codigo: string;
  nome: string;
  complemento: string;
  identificacao: string;
};

export type Setor = {
  id: number;
  area: number;
  codigo: string;
  nome: string;
  complemento: string;
  identificacao: string;
};

/** Lista de clientes já no formato do Combobox (com CNPJ/cidade para desambiguar). */
export function useClientes() {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    api<Paginated<Cliente>>("/clientes/?page_size=1000")
      .then((d) => setClientes(d.results))
      .catch(() => setClientes([]))
      .finally(() => setCarregando(false));
  }, []);

  const opcoes: Opcao[] = clientes.map((c) => ({
    id: c.id,
    label: c.nome_fantasia || c.nome,
    hint: [c.cnpj, c.cidade_uf].filter(Boolean).join(" · "),
  }));

  return { clientes, opcoes, carregando };
}

/**
 * Cascata Cliente → Área → Setor.
 * Ao trocar o cliente, as áreas recarregam e o setor é limpo (e vice-versa).
 */
export function useAreasSetores(clienteId: number | "", areaId: number | "") {
  const [areas, setAreas] = useState<Area[]>([]);
  const [setores, setSetores] = useState<Setor[]>([]);

  useEffect(() => {
    if (!clienteId) {
      setAreas([]);
      return;
    }
    api<Paginated<Area>>(`/areas/?cliente=${clienteId}&page_size=1000`)
      .then((d) => setAreas(d.results))
      .catch(() => setAreas([]));
  }, [clienteId]);

  useEffect(() => {
    if (!areaId) {
      setSetores([]);
      return;
    }
    api<Paginated<Setor>>(`/setores/?area=${areaId}&page_size=1000`)
      .then((d) => setSetores(d.results))
      .catch(() => setSetores([]));
  }, [areaId]);

  const opcoesAreas: Opcao[] = areas.map((a) => ({ id: a.id, label: a.identificacao }));
  const opcoesSetores: Opcao[] = setores.map((s) => ({ id: s.id, label: s.identificacao }));

  return { areas, setores, opcoesAreas, opcoesSetores };
}
