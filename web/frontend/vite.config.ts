import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// v0.95.1: Vite build → web/frontend/dist, Flask 托管 (web/api/app.py teacher_assets).
// dev: Vite 5174, proxy /api → Flask 5173 (与 03-roadmap §v0.95 决策一致).
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    port: 5174,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5173",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          // 拆 echarts / react 独立 chunk, 避免单包 >500kB (产品 Demo 首屏可缓存)
          echarts: ["echarts"],
          vendor: ["react", "react-dom", "react-router-dom", "@tanstack/react-query"],
        },
      },
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
