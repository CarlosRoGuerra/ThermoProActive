// Mesma tela de lançamento de medições que a equipe interna usa em
// /inspecoes/:id — só "Gerar laudo" fica de fora pra quem não é da equipe
// técnica (emitir laudo é responsabilidade profissional, não gestão do
// próprio parque). O resto (lançar vibração/termografia/outros ensaios)
// já funciona igual, porque a página lê `parque:gerenciar`, não mais
// "é da equipe interna?".
export { default } from "@/app/(admin)/inspecoes/[id]/page";
