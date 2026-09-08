import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/projects": "http://localhost:8000",
      "/stats": "http://localhost:8000",
      "/contractors": "http://localhost:8000",
    },
  },
});
