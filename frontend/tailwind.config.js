/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Ayurveda-leaning accent, used sparingly.
        aiia: {
          50: '#f0f9f4',
          100: '#dcf1e4',
          500: '#2f8f5b',
          600: '#25734a',
          700: '#1d5a3a',
        },
      },
    },
  },
  plugins: [],
}
