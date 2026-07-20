/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,jsx}", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "var(--pe-color-primary-50)",
          100: "var(--pe-color-primary-100)",
          200: "var(--pe-color-primary-200)",
          300: "var(--pe-color-primary-300)",
          400: "var(--pe-color-primary-400)",
          500: "var(--pe-color-primary-500)",
          600: "var(--pe-color-primary-600)",
          700: "var(--pe-color-primary-700)",
          800: "var(--pe-color-primary-800)",
          900: "var(--pe-color-primary-900)",
        },
        slate: {
          50: "var(--pe-color-gray-50)",
          100: "var(--pe-color-gray-100)",
          200: "var(--pe-color-gray-200)",
          300: "var(--pe-color-gray-300)",
          400: "var(--pe-color-gray-400)",
          500: "var(--pe-color-gray-500)",
          600: "var(--pe-color-gray-600)",
          700: "var(--pe-color-gray-700)",
          800: "var(--pe-color-gray-800)",
          900: "var(--pe-color-gray-900)",
        },
        gray: {
          50: "var(--pe-color-gray-50)",
          100: "var(--pe-color-gray-100)",
          200: "var(--pe-color-gray-200)",
          300: "var(--pe-color-gray-300)",
          400: "var(--pe-color-gray-400)",
          500: "var(--pe-color-gray-500)",
          600: "var(--pe-color-gray-600)",
          700: "var(--pe-color-gray-700)",
          800: "var(--pe-color-gray-800)",
          900: "var(--pe-color-gray-900)",
        },
        white: "var(--pe-color-bg-primary)",
        black: "var(--pe-color-text-primary)",
        amber: {
          50: "color-mix(in srgb, var(--pe-color-warning) 12%, var(--pe-color-bg-primary))",
          400: "var(--pe-color-warning)",
          700: "var(--pe-color-text-warning)",
        },
        red: {
          50: "color-mix(in srgb, var(--pe-color-error) 12%, var(--pe-color-bg-primary))",
          200: "color-mix(in srgb, var(--pe-color-error) 28%, var(--pe-color-bg-primary))",
          700: "color-mix(in srgb, var(--pe-color-error) 72%, var(--pe-color-text-primary))",
        },
      },
      fontFamily: {
        sans: ["var(--pe-font-family-body)"],
        mono: ["var(--pe-font-family-mono)"],
      },
    },
  },
  plugins: [],
};
