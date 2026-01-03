import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// BASE_PATH lets us build for GitHub Pages project URLs (e.g. /trazimstan/).
const base = process.env.BASE_PATH ?? "/";

export default defineConfig({
  base,
  plugins: [react()],
  build: {
    outDir: "dist",
  },
});

