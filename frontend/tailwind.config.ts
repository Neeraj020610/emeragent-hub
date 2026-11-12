import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        hub: {
          bg: "#f8fafc",
          surface: "#ffffff",
          navy: "#0f172a",
          navymuted: "#334155",
          primary: "#1d4ed8",
          primaryhover: "#1e40af",
          teal: "#0f766e",
          border: "#e2e8f0",
          borderlight: "#f1f5f9",
          cardbg: "#ffffff",
        },
      },
    },
  },
  plugins: [],
};
export default config;
