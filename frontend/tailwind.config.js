/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        jnj: { DEFAULT: "#D51900", dark: "#A31300", light: "#FF4D33" },
        clinical: { DEFAULT: "#22D3EE", dark: "#0891B2" },
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
      keyframes: {
        pulseRing: { "0%": { boxShadow: "0 0 0 0 rgba(34,211,238,0.6)" }, "100%": { boxShadow: "0 0 0 10px rgba(34,211,238,0)" } },
      },
      animation: { pulseRing: "pulseRing 1.2s ease-out infinite" },
    },
  },
  plugins: [],
};
