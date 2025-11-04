/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    '../templates/**/*.html',
    '../../templates/**/*.html',
    '../../**/templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        // Custom color palette if needed
      },
    },
  },
  darkMode: 'media', // Use 'class' for manual dark mode toggle, 'media' for system preference
  plugins: [
    require("daisyui")
  ],
  // daisyUI config
  daisyui: {
    themes: ["light", "dark"], // Enable both light and dark themes
    darkTheme: "dark", // Name of the dark theme to use
    base: true, // Apply base styles
    styled: true, // Apply theme colors
    utils: true, // Apply utility classes
    prefix: "", // Prefix for daisyUI classes
    logs: false, // Disable logging
    themeRoot: ":root", // The element that receives theme color CSS variables
  },
}