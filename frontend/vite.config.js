import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true, // 모든 네트워크 인터페이스에서 접속 허용 (Tailscale·LAN으로 다른 기기 접속)
    proxy: {
      // 프론트의 /api 요청을 백엔드(8000)로 전달 (PC 내부에서 프록시되므로 backend는 127.0.0.1 그대로 OK)
      "/api": "http://127.0.0.1:8000",
    },
  },
});
