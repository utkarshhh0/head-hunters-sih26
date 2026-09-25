/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        institutional: {
          bg: '#0A0E17',
          panel: '#101726',
          panelAlt: '#141D2E',
          border: '#1E293B',
          borderMuted: '#152033',
          borderAccent: '#334155',
          textMuted: '#64748B',
          textSecondary: '#94A3B8',
          textPrimary: '#F1F5F9',
          accent: '#2563EB',
          accentHover: '#1D4ED8',
          accentGlow: 'rgba(37, 99, 235, 0.15)',
        }
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', '"Liberation Mono"', '"Courier New"', 'monospace'],
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
