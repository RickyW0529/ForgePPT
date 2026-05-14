/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        deepblue: {
          50: '#E8EDF3',
          100: '#D1DBE7',
          200: '#BEE3F8',
          300: '#63B3ED',
          400: '#3182CE',
          500: '#2E4A62',
          600: '#1E3A5F',
          700: '#1A365D',
          800: '#0F1D2E',
          900: '#0A1525',
        },
        surface: '#F7FAFC',
      },
    },
  },
  plugins: [],
};
