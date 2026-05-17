import { defineConfig } from "vite";

export default defineConfig({
  esbuild: {
    jsx: "automatic",
  },
  server: {
    host: "0.0.0.0",
    port: 5186,
  },
  preview: {
    host: "0.0.0.0",
    port: 5186,
  },
});
