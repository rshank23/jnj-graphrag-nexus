/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Ink-toned neutral scale (blue undertone) used across the whole UI in place of Tailwind's default slate.
        slate: {
          50: "#F5F7FB",
          100: "#EBEFF6",
          200: "#D6DDE8",
          300: "#B3BDCD",
          400: "#8A96AA",
          500: "#657187",
          600: "#475266",
          700: "#2D3647",
          800: "#1B2231",
          900: "#111723",
          950: "#080B13",
        },
        jnj: { DEFAULT: "#E1251B", dark: "#B31B13", light: "#FF5A4A" },
        clinical: { DEFAULT: "#5CCFE6", dark: "#2BA3C2", light: "#A6E9F5" },
        gold: { DEFAULT: "#D9B26F", light: "#EED7A8" },
      },
      fontFamily: {
        sans: ["'Inter Variable'", "Inter", "Segoe UI", "system-ui", "sans-serif"],
        display: ["'Instrument Serif'", "Georgia", "serif"],
        mono: ["'JetBrains Mono Variable'", "JetBrains Mono", "Consolas", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 20px 50px -24px rgba(0,0,0,0.65)",
        glow: "0 0 0 1px rgba(92,207,230,0.25), 0 8px 30px -8px rgba(92,207,230,0.35)",
        brand: "0 10px 30px -10px rgba(225,37,27,0.65)",
      },
      keyframes: {
        pulseRing: { "0%": { boxShadow: "0 0 0 0 rgba(92,207,230,0.55)" }, "100%": { boxShadow: "0 0 0 10px rgba(92,207,230,0)" } },
        fadeUp: { "0%": { opacity: "0", transform: "translateY(6px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
        shimmer: { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
      },
      animation: {
        pulseRing: "pulseRing 1.2s ease-out infinite",
        fadeUp: "fadeUp 0.35s cubic-bezier(0.2, 0.7, 0.2, 1) both",
        shimmer: "shimmer 2.4s linear infinite",
      },
    },
  },
  plugins: [],
};
