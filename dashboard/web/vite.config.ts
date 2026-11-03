import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the Python server (127.0.0.1:8765) provides /api; Vite proxies it.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
});
