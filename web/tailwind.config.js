/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Re-toned to the real logo (navy field, magenta-to-purple cube) as
        // of Phase 6 — see docs/DOCUMENTATION.md §10. `brand` (navy) is the
        // primary surface/text/nav color, used broadly exactly like the old
        // blue scale was; `accent` (magenta) is new and deliberately used
        // sparingly, only on the highest-emphasis CTAs (search, primary
        // booking actions, hero marketing CTAs) — not swapped in everywhere
        // `brand` already was, per the "accent sparingly" design call.
        brand: {
          50: "#eef3fa",
          100: "#dde7f4",
          200: "#c1d0ea",
          300: "#93aedb",
          400: "#6089c8",
          500: "#3a6bb5",
          600: "#21529a",
          700: "#17417f",
          800: "#10306a",
          900: "#0a1f45",
        },
        accent: {
          50: "#fbeef6",
          100: "#f6d7eb",
          200: "#edb0d6",
          300: "#e085bd",
          400: "#cf5fa3",
          500: "#b83e89",
          600: "#97316f",
          700: "#772a84",
          800: "#5c2264",
          900: "#401648",
        },
      },
    },
  },
  plugins: [],
};
