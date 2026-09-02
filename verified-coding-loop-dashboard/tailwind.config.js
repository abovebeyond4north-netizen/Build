/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#07111f',
        panel: '#0c1b2f',
        line: '#1e3a5f',
        tealglow: '#2dd4bf',
        blueglow: '#38bdf8'
      },
      boxShadow: {
        glow: '0 0 40px rgba(45, 212, 191, 0.15)'
      }
    }
  },
  plugins: []
};
