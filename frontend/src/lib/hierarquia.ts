"use client";

import { useMemo } from "react";
import { useLista } from "./recurso";
import type { Cliente } from "./types";
import type { Opcao } from "@/components/combobox";

/**
 * Cascata da hierarquia de locais: Cliente → Área → Setor.
 *
 * Todas as buscas passam por `useLista`, que trata carregando/erro/cancelamento
 * num lugar só — antes cada hook fazia `.catch(() => setX([]))`, engolindo a
 * falha e mostrando um combo vazio como se não houvesse cadastro.
 */

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

/**
 * Clientes no formato do Combobox (com CNPJ/cidade para desambiguar homônimos).
 *
 * @param habilitado Passe `false` para não buscar — é o caso do Portal do
 *   Cliente, onde não existe seleção de cliente (o usuário É o cliente).
 */
export function useClientes(habilitado = true) {
  const { itens, carregando, falha, recarregar } = useLista<Cliente>(
    habilitado ? "/clientes/?page_size=500" : null,
    "lista de clientes"
  );

  const opcoes: Opcao[] = useMemo(
    () =>
      itens.map((c) => ({
        id: c.id,
        label: c.nome_fantasia || c.nome,
        hint: [c.cnpj, c.cidade_uf].filter(Boolean).join(" · "),
      })),
    [itens]
  );

  return { clientes: itens, opcoes, carregando, falha, recarregar };
}

/**
 * Áreas e setores em cascata. Trocar o cliente recarrega as áreas; trocar a
 * área recarrega os setores. Sem seleção acima, a lista de baixo fica vazia por
 * definição (e não por erro) — o `null` evita a requisição inútil.
 */
export function useAreasSetores(clienteId: number | "", areaId: number | "") {
  const areas = useLista<Area>(clienteId ? `/areas/?cliente=${clienteId}&page_size=500` : null, "áreas");
  const setores = useLista<Setor>(areaId ? `/setores/?area=${areaId}&page_size=500` : null, "setores");

  const opcoesAreas: Opcao[] = useMemo(
    () => areas.itens.map((a) => ({ id: a.id, label: a.identificacao })),
    [areas.itens]
  );
  const opcoesSetores: Opcao[] = useMemo(
    () => setores.itens.map((s) => ({ id: s.id, label: s.identificacao })),
    [setores.itens]
  );

  return {
    areas: areas.itens,
    setores: setores.itens,
    opcoesAreas,
    opcoesSetores,
    carregando: areas.carregando || setores.carregando,
  };
}
