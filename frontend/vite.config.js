import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // El frontend llama a /api/* y vite lo reenvia a la API quitando el prefijo.
      // Asi en desarrollo no hace falta CORS ni configurar VITE_API_URL.
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, "")
      }
    }
  }
});

