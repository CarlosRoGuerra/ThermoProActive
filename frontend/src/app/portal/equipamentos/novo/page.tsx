"use client";

// Mesmo formulário que a equipe interna usa em /equipamentos/novo — o Master
// do cliente entra pelo Portal, mas é a MESMA tela (nada duplicado). O
// `ClienteAtivoProvider` já resolve sozinho o cliente certo para quem está
// logado como Portal, então o formulário nem precisa saber que veio daqui.
import { EquipamentoForm } from "@/app/(admin)/equipamentos/equipamento-form";

export default function PortalNovoEquipamentoPage() {
  return <EquipamentoForm />;
}
