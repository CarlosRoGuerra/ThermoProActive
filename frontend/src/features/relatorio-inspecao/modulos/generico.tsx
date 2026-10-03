import { criarModuloInspecao } from "./inspecao/modulo";

/* Inspeção genérica (ex.: Análise Sensitiva Sensorial) — escolhida de propósito no
   cadastro da tecnologia. A folha da OSP fica com o cabeçalho, o Grau de Risco, a
   foto do equipamento, o Planejamento e o Retorno de Informação; sem bloco de
   medições e sem quadros de imagem de outra técnica (nada de Tendência/Espectro
   ou amplitudes). A carta não tem tabela normativa; glossário e considerações
   neutros vêm do backend (relatorio_tecnico/generico.py). */

function SemMedicoes() {
  return null;
}

export const MODULO_INSPECAO_GENERICA = criarModuloInspecao({
  chave: "INSPECAO_GENERICA",
  Medicoes: SemMedicoes,
  quadros: [],
});
