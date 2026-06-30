import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development the console calls the API through this proxy, as nginx does in staging and production.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": { target: "http://localhost:8000", rewrite: (path) => path.replace(/^\/api/, "") } } },
  test: { environment: "jsdom" },
});
