import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// API_PROXY_TARGET: 개발 서버의 /api 프록시 대상.
//   - docker compose 내부: http://api:8000 (기본값)
//   - 호스트에서 직접 실행: API_PROXY_TARGET=http://localhost:8000
const apiTarget = process.env.API_PROXY_TARGET ?? "http://api:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
});
