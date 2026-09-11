/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "-apple-system", "BlinkMacSystemFont", "Segoe UI", "system-ui",
          "Roboto", "Helvetica Neue", "Arial", "sans-serif",
        ],
      },
      colors: {
        brand: {
          50: "#eef6ff", 100: "#d9ecff", 500: "#2563eb", 600: "#1d4ed8", 700: "#1e40af",
        },
        conciliado: "#0f766e",
        divergente: "#b42318",
        pendente: "#b54708",
      },
    },
  },
  plugins: [],
};
