/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        burgundy: {
          50: '#fdf2f2',
          100: '#fce7e7',
          200: '#f9d1d1',
          300: '#f2adad',
          400: '#e47b7b',
          500: '#cf4f4f',
          600: '#b53333',
          700: '#962424',
          800: '#7c1e1e',
          900: '#590907', // Primary
          950: '#390403',
        },
        sage: {
          50: '#f6f7f5',
          100: '#eceee9',
          200: '#d9ded3',
          300: '#c0c6b7',
          400: '#A5A79B', // Secondary
          500: '#898b7e',
          600: '#6c6e62',
          700: '#56574e',
          800: '#46473f',
          900: '#3c3d36',
        },
        cream: {
          50: '#fcfaf7',
          100: '#f7f2ea',
          200: '#E8D2B5', // Accent
          300: '#ddbf99',
          400: '#d1aa7b',
          500: '#c3935e',
          600: '#b27a48',
          700: '#945f3b',
          800: '#7a4e34',
          900: '#63412d',
        },
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-subtle': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'flow-fast': 'flow 1.5s linear infinite',
      },
      keyframes: {
        flow: {
          '0%': { strokeDashoffset: '24' },
          '100%': { strokeDashoffset: '0' },
        },
      },
    },
  },
  plugins: [],
}
