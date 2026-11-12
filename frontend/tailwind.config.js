import defaultColors from "tailwindcss/colors";

// Light theme: components were authored against a dark scale, so every scale is mirrored
// (50<->950, 100<->900 ...). e.g. `bg-slate-950` is now the page, `text-red-300` reads as red-700,
// and `bg-red-950/40` becomes a soft red-50 tint.
const mirror = (scale) =>
  Object.fromEntries(Object.entries(scale).map(([k]) => [k, scale[String(1000 - Number(k))] ?? scale[k]]));

const ACCENTS = ["red", "orange", "amber", "yellow", "lime", "green", "emerald", "teal", "cyan", "sky", "blue", "indigo", "violet", "purple", "fuchsia", "pink", "rose"];

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ...Object.fromEntries(ACCENTS.map((c) => [c, mirror(defaultColors[c])])),
        // Neutral ink scale: 950 = page, 900 = card surface, 800/700 = borders, 500/400 = muted text, 100/50 = headings.
        slate: {
          50: "#0B1220",
          100: "#141C2E",
          200: "#222C40",
          300: "#36415A",
          400: "#4F5B72",
          500: "#667189",
          600: "#8F99AB",
          700: "#CBD3DF",
          800: "#E2E7EF",
          900: "#FFFFFF",
          950: "#F4F6FA",
        },
        // `white` utilities (headings, hairline overlays/borders) now resolve to ink; use `snow` for true white.
        white: "#0B1220",
        snow: "#FFFFFF",
        jnj: { DEFAULT: "#D51900", dark: "#A31300", light: "#C0260F" },
        clinical: { DEFAULT: "#0A7C93", dark: "#075F72", light: "#086A7E" },
        gold: { DEFAULT: "#A9771F", light: "#9A6A16" },
      },
      fontFamily: {
        sans: ["'Inter Variable'", "Inter", "Segoe UI", "system-ui", "sans-serif"],
        display: ["'Instrument Serif'", "Georgia", "serif"],
        mono: ["'JetBrains Mono Variable'", "JetBrains Mono", "Consolas", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 2px rgba(16,24,40,0.04), 0 8px 24px -12px rgba(16,24,40,0.10)",
        glow: "0 0 0 1px rgba(10,124,147,0.18), 0 12px 30px -12px rgba(10,124,147,0.28)",
        brand: "0 8px 20px -8px rgba(213,25,0,0.45)",
      },
      keyframes: {
        pulseRing: { "0%": { boxShadow: "0 0 0 0 rgba(16,185,129,0.45)" }, "100%": { boxShadow: "0 0 0 8px rgba(16,185,129,0)" } },
        fadeUp: { "0%": { opacity: "0", transform: "translateY(6px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
        shimmer: { "0%": { backgroundPosition: "-200% 0" }, "100%": { backgroundPosition: "200% 0" } },
      },
      animation: {
        pulseRing: "pulseRing 1.4s ease-out infinite",
        fadeUp: "fadeUp 0.35s cubic-bezier(0.2, 0.7, 0.2, 1) both",
        shimmer: "shimmer 2.4s linear infinite",
      },
    },
  },
  plugins: [],
};
