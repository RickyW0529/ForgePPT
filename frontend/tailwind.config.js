/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        deepblue: {
          50: '#EDF3FA',
          100: '#D8E5F4',
          200: '#B8CEE7',
          300: '#86A9D2',
          400: '#5E87BA',
          500: '#3E688F',
          600: '#2D5275',
          700: '#23405B',
          800: '#182E44',
          900: '#0F1D2E',
        },
        surface: '#F4F7FB',
        panel: '#FFFFFF',
        border: '#D9E2EC',
        muted: '#64748B',
      },
      boxShadow: {
        soft: '0 10px 30px rgba(15, 23, 42, 0.06)',
        insetSoft: 'inset 0 1px 0 rgba(255, 255, 255, 0.65)',
        card: '0 2px 8px rgba(15, 23, 42, 0.08), 0 1px 2px rgba(15, 23, 42, 0.04)',
      },
      borderRadius: {
        xl2: '1.25rem',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.2s ease-out',
      },
    },
  },
  plugins: [],
};
