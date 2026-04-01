import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

const rawBasePath = process.env.VITE_BASE_PATH || "/mail/";
const normalizedBasePath = rawBasePath.endsWith("/") ? rawBasePath : `${rawBasePath}/`;

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  base: normalizedBasePath,
  server: {
    host: "::",
    port: 8080,
    proxy: {
      "/mail/api": {
        target: "http://127.0.0.1:5001",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/mail/, ""),
      },
      "/api": {
        target: "http://127.0.0.1:5001",
        changeOrigin: true,
      },
    },
    hmr: {
      overlay: false,
    },
  },
  plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
