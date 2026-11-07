"use client";

import { motion, useReducedMotion } from "framer-motion";
import { EASE_OUT } from "@/components/motion";

// Transição suave ao navegar entre rotas (App Router remonta o template a cada navegação).
export default function Template({ children }: { children: React.ReactNode }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      // rota-transicao: a impressão anula a animação (globals.css) — imprimir no meio dela
      // saía com o conteúdo deslocado e semitransparente.
      className="rota-transicao"
      initial={{ opacity: 0, y: reduce ? 0 : 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: EASE_OUT }}
    >
      {children}
    </motion.div>
  );
}
