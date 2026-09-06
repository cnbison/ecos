import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import pkg from "./package.json";

// v0.95.1: Vite build → web/frontend/dist, Flask 托管 (web/api/app.py teacher_assets).
// dev: Vite 5174, proxy /api → Flask 5173 (与 03-roadmap §v0.95 决策一致).
// v0.96: __APP_VERSION__ 编译期注入 package.json version, 设置页显示单一权威源 (防 v0.51.4 hardcoded 教训).
export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
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
      // v0.96: 多页 — teacher SPA (index.html) + student SPA (student.html), 共享一套工具链
      // v0.98.0 (a-c): + parent SPA (parent.html) 第三入口
      input: {
        teacher: "index.html",
        student: "student.html",
        parent: "parent.html",
      },
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
