# YF Monitor Console

独立的 `Vue 3 + Vite + Element Plus` 控制台，用于展示智能戒指后端的设备、测量、告警和总览数据。

## 运行

```powershell
cd console
npm install
Copy-Item .env.example .env
npm run dev
```

默认通过 Vite 代理访问 `http://127.0.0.1:8000` 的 Django 后端。
