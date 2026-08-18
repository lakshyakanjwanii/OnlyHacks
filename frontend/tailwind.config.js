/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"]
      },
      colors: {
        ink: "#07111f",
        panel: "#0d1b2a",
        tealx: "#16c7b7",
        cyanx: "#42d9ff",
        danger: "#ff5b64",
        amberx: "#f6b84b"
      },
      boxShadow: {
        glow: "0 0 35px rgba(22,199,183,.12)"
      }
    }
  },
  plugins: []
};
