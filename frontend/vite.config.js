import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 프론트의 /api 요청을 백엔드(8000)로 전달
      "/api": "http://127.0.0.1:8000",
    },
  },
});
