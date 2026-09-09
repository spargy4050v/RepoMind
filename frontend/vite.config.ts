import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/auth": "http://localhost:8000",
      "/verify": "http://localhost:8000",
      "/analysis": "http://localhost:8000",
      "/history": "http://localhost:8000",
      "/upload": "http://localhost:8000",
      "/projects": "http://localhost:8000",
      "/stats": "http://localhost:8000",
      "/contractors": "http://localhost:8000",
      "/context": "http://localhost:8000",
      "/simulate": "http://localhost:8000",
      "/alerts": "http://localhost:8000",
    },
  },
});
