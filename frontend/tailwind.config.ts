import type { Config } from "tailwindcss";

/**
 * Design System ThermoProActive — escalas.
 *
 * As cores apontam SEMPRE para CSS variables (definidas em src/app/globals.css),
 * nunca para literais: trocar a identidade visual do produto é editar um arquivo.
 *
 * Convenção de nomes:
 *   primary / secondary  → identidade da marca
 *   success / warning / danger / info → estado (nunca usados como identidade)
 *   chrome-*             → navegação (sidebar/topbar), aço escuro nos dois temas
 *   viz-*                → séries de gráfico (categórico, não semântico)
 */
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: {
          DEFAULT: "var(--surface)",
          muted: "var(--surface-muted)",
          raised: "var(--surface-raised)",
        },
        "surface-muted": "var(--surface-muted)",
        overlay: "var(--overlay)",
        border: {
          DEFAULT: "var(--border)",
          strong: "var(--border-strong)",
        },
        "border-strong": "var(--border-strong)",
        fg: {
          DEFAULT: "var(--fg)",
          muted: "var(--fg-muted)",
          subtle: "var(--fg-subtle)",
        },
        "fg-muted": "var(--fg-muted)",
        "fg-subtle": "var(--fg-subtle)",

        primary: {
          DEFAULT: "var(--primary)",
          hover: "var(--primary-hover)",
          active: "var(--primary-active)",
          fg: "var(--primary-fg)",
          subtle: "var(--primary-subtle)",
          "subtle-fg": "var(--primary-subtle-fg)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          subtle: "var(--secondary-subtle)",
          "subtle-fg": "var(--secondary-subtle-fg)",
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
        info: {
          DEFAULT: "var(--info)",
          subtle: "var(--info-subtle)",
          fg: "var(--info-fg)",
        },

        chrome: {
          DEFAULT: "var(--chrome)",
          muted: "var(--chrome-muted)",
          active: "var(--chrome-active)",
          fg: "var(--chrome-fg)",
          "fg-muted": "var(--chrome-fg-muted)",
          "fg-subtle": "var(--chrome-fg-subtle)",
          border: "var(--chrome-border)",
        },

        /* Compatibilidade dos documentos (Relatório Técnico e dossiê), que
           estão no conteúdo aprovado e usam estes nomes. Mesma cor de primary. */
        accent: {
          DEFAULT: "var(--accent)",
          hover: "var(--accent-hover)",
          fg: "var(--accent-fg)",
          subtle: "var(--accent-subtle)",
          "subtle-fg": "var(--accent-subtle-fg)",
          "2": "var(--accent-2)",
        },

        viz: {
          1: "var(--viz-1)",
          2: "var(--viz-2)",
          3: "var(--viz-3)",
          4: "var(--viz-4)",
          5: "var(--viz-5)",
        },
      },

      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "Consolas", "monospace"],
      },

      /* Escala tipográfica com line-height e tracking amarrados ao tamanho —
         evita cada tela escolher o seu. */
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.01em" }], // 11px — meta/rótulo
        xs: ["0.75rem", { lineHeight: "1.125rem" }], // 12px — auxiliar
        sm: ["0.8125rem", { lineHeight: "1.25rem" }], // 13px — densidade de painel
        base: ["0.875rem", { lineHeight: "1.375rem" }], // 14px — corpo
        md: ["0.9375rem", { lineHeight: "1.5rem" }], // 15px — corpo do portal
        lg: ["1.0625rem", { lineHeight: "1.625rem", letterSpacing: "-0.005em" }],
        xl: ["1.25rem", { lineHeight: "1.75rem", letterSpacing: "-0.012em" }], // título de página
        "2xl": ["1.5rem", { lineHeight: "2rem", letterSpacing: "-0.018em" }],
        "3xl": ["1.875rem", { lineHeight: "2.25rem", letterSpacing: "-0.022em" }],
        "4xl": ["2.25rem", { lineHeight: "2.5rem", letterSpacing: "-0.026em" }],
      },

      /* Passos extras para densidade de painel (base 4px do Tailwind mantida). */
      spacing: {
        4.5: "1.125rem",
        13: "3.25rem",
        17: "4.25rem",
        18: "4.5rem",
        rail: "4.25rem", // trilho da sidebar recolhida (68px)
        sidebar: "16rem", // sidebar expandida (256px)
        topbar: "3.5rem", // altura da topbar (56px)
      },

      borderRadius: {
        sm: "0.25rem",
        DEFAULT: "0.375rem",
        md: "0.5rem",
        lg: "0.625rem", // 10px — raio padrão de controle
        xl: "0.875rem", // 14px — card
        "2xl": "1.125rem", // 18px — painel / modal
        "3xl": "1.5rem",
      },

      boxShadow: {
        /* Elevação discreta: sombra indica camada, não decora. */
        xs: "0 1px 2px 0 rgb(11 18 32 / 0.05)",
        sm: "0 1px 2px 0 rgb(11 18 32 / 0.06), 0 1px 3px 0 rgb(11 18 32 / 0.05)",
        md: "0 2px 8px -2px rgb(11 18 32 / 0.09), 0 2px 4px -2px rgb(11 18 32 / 0.05)",
        lg: "0 12px 28px -8px rgb(11 18 32 / 0.16)",
        xl: "0 24px 48px -12px rgb(11 18 32 / 0.24)",
        focus: "0 0 0 3px var(--primary-ring)",
        "focus-danger": "0 0 0 3px var(--danger-ring)",
        rail: "8px 0 24px -8px rgb(11 18 32 / 0.22)",
      },

      /* Camadas nomeadas — fim do z-[9999] arbitrário. */
      zIndex: {
        base: "0",
        raised: "10",
        sticky: "20",
        rail: "30",
        dropdown: "40",
        drawer: "50",
        modal: "60",
        toast: "70",
        tooltip: "80",
      },

      screens: {
        xs: "375px", // limite inferior real de uso em campo
        "3xl": "1600px",
      },

      keyframes: {
        shimmer: { "100%": { transform: "translateX(100%)" } },
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "slide-down": {
          from: { opacity: "0", transform: "translateY(-6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        /* Pulso de atenção para leitura crítica em curso (2 ciclos, não infinito:
           movimento contínuo em painel de operação vira ruído). */
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 var(--danger-ring)" },
          "70%": { boxShadow: "0 0 0 6px transparent" },
          "100%": { boxShadow: "0 0 0 0 transparent" },
        },
      },
      animation: {
        shimmer: "shimmer 1.4s infinite",
        "fade-in": "fade-in 0.18s ease-out",
        "slide-up": "slide-up 0.2s cubic-bezier(0.22, 1, 0.36, 1)",
        "slide-down": "slide-down 0.2s cubic-bezier(0.22, 1, 0.36, 1)",
        "pulse-ring": "pulse-ring 1.6s ease-out 2",
      },
      transitionTimingFunction: {
        "out-soft": "cubic-bezier(0.22, 1, 0.36, 1)",
      },
      transitionDuration: {
        instant: "100ms",
        fast: "150ms",
        normal: "200ms",
        slow: "300ms",
      },
    },
  },
  plugins: [],
};

export default config;
