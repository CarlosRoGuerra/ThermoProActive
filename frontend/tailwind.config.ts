import type { Config } from "tailwindcss";

/**
 * Tokens de design centralizados (ThermoProActive).
 * As cores apontam para CSS variables definidas em globals.css — um único lugar
 * para ajustar a paleta (accent indigo, neutros slate, semânticas de status).
 */
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        "surface-muted": "var(--surface-muted)",
        border: "var(--border)",
        "border-strong": "var(--border-strong)",
        fg: "var(--fg)",
        "fg-muted": "var(--fg-muted)",
        "fg-subtle": "var(--fg-subtle)",
        accent: {
          DEFAULT: "var(--accent)",
          hover: "var(--accent-hover)",
          fg: "var(--accent-fg)",
          subtle: "var(--accent-subtle)",
          "subtle-fg": "var(--accent-subtle-fg)",
          "2": "var(--accent-2)",
        },
        success: {
          DEFAULT: "var(--success)",
          subtle: "var(--success-subtle)",
          fg: "var(--success-fg)",
        },
        warning: {
          DEFAULT: "var(--warning)",
          subtle: "var(--warning-subtle)",
          fg: "var(--warning-fg)",
        },
        danger: {
          DEFAULT: "var(--danger)",
          subtle: "var(--danger-subtle)",
          fg: "var(--danger-fg)",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "Consolas", "monospace"],
      },
      borderRadius: {
        lg: "0.625rem", // 10px — raio padrão sutil e consistente
        xl: "0.875rem", // 14px
        "2xl": "1.125rem", // 18px
      },
      boxShadow: {
        // Sombras discretas, só para elevação (cards, dropdowns, modais).
        xs: "0 1px 2px 0 rgb(15 23 42 / 0.04)",
        sm: "0 1px 2px 0 rgb(15 23 42 / 0.05), 0 1px 3px 0 rgb(15 23 42 / 0.05)",
        md: "0 2px 8px -2px rgb(15 23 42 / 0.08), 0 2px 4px -2px rgb(15 23 42 / 0.05)",
        lg: "0 12px 28px -8px rgb(15 23 42 / 0.14)",
        focus: "0 0 0 3px var(--accent-ring)",
      },
      keyframes: {
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        shimmer: "shimmer 1.4s infinite",
      },
      transitionTimingFunction: {
        "out-soft": "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
