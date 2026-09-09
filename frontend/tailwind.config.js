/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Frost Bank Blue palette
        frost: {
          navy: "#0F2A4A",      // deep navy — primary brand
          deep: "#1E293B",      // very dark navy — surfaces/text
          slate: "#475569",     // medium slate blue — secondary text
          steel: "#64748B",     // muted slate
          light: "#F1F5F9",     // light gray — backgrounds
          surface: "#F8FAFC",   // near-white surface
          mist: "#E2E8F0",      // borders
        },
        gold: {
          DEFAULT: "#C9A227",   // gold accent
          soft: "#E7CB6B",
        },
        status: {
          success: "#10B981",
          warning: "#F59E0B",
          danger: "#EF4444",
          info: "#3B82F6",
        },
      },
      fontFamily: {
        display: ['"Playfair Display"', "Georgia", "serif"],
        sans: ['"Open Sans"', "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 42, 74, 0.05), 0 4px 16px rgba(15, 42, 74, 0.06)",
        panel: "0 2px 4px rgba(15, 42, 74, 0.06), 0 8px 24px rgba(15, 42, 74, 0.08)",
      },
      keyframes: {
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        fadeIn: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        fadeIn: "fadeIn 0.4s ease-out both",
      },
    },
  },
  plugins: [],
};
