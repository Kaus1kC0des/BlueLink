import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build to ui/dist, which the Python service serves from "/".
// The dev server proxies the WebSocket to the local service on :8760.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/ws": {
        target: "ws://127.0.0.1:8760",
        ws: true,
      },
    },
  },
});
