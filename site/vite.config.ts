import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Relative base so the build works under any path, including GitHub Pages.
export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  build: {
    // One page, and its data (site-data.json) is needed on first paint.
    chunkSizeWarningLimit: 700,
  },
});
