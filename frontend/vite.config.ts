import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/demo-cases": "http://127.0.0.1:8000",
      "/reports": "http://127.0.0.1:8000",
      "/extractions": "http://127.0.0.1:8000",
      "/analysis": "http://127.0.0.1:8000"
    }
  }
});
