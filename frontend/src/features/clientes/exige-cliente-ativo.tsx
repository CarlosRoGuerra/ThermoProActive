"use client";

import Link from "next/link";
import { Building2 } from "lucide-react";
import { Button, Card, EmptyState } from "@/components/ds";

/**
 * Aviso padrão das telas que só fazem sentido dentro do ambiente de um cliente
 * (equipamentos, áreas, setores, rotas).
 *
 * Antes cada tela escrevia o seu próprio texto e algumas simplesmente ficavam
 * vazias, sem dizer que faltava escolher o cliente. Aqui a explicação é uma só,
 * e o caminho para resolver está no próprio aviso.
 */
export function ExigeClienteAtivo({ oQue }: { oQue: string }) {
  return (
    <Card padding={false}>
      <EmptyState
        icon={Building2}
        title="Escolha o cliente que você está atendendo"
        description={`${oQue} pertencem a um cliente. Ative um cliente no seletor do topo — ou na lista de clientes — para ver e cadastrar os dados dele.`}
        action={
          <Link href="/clientes">
            <Button icon={Building2}>Ir para Clientes</Button>
          </Link>
        }
        comoFunciona={[
          "Abra Clientes e escolha a empresa atendida.",
          "O sistema passa a trabalhar dentro do ambiente dela.",
          "Áreas, setores, equipamentos e rotas já aparecem filtrados.",
        ]}
      />
    </Card>
  );
}
