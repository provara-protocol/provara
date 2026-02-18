import type { Config } from 'tailwindcss';

export default {
  content: ['./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        provara: {
          50:  '#f5f3ff',
          100: '#ede9fe',
          300: '#c4b5fd',
          500: '#a78bfa',
          600: '#9333ea',
          700: '#7c3aed',
          800: '#6d28d9',
          900: '#2d1b4e',
        }
      }
    }
  },
  plugins: []
} satisfies Config;
