# YF Monitor

智能房颤监测项目的后端与控制台工作区。

当前仓库中已经有两套彼此独立的内容：

- [backend](backend)：`Django + DRF` 后端，负责认证、设备绑定、原始包接收、协议解析、风险分析、历史查询、告警处理。
- [console](console)：`Vue 3 + Vite + Element Plus` 控制台，给后端开发、前端开发、演示使用。

说明：

- `study` 目录保留原始材料和微信小程序 BLE 代码，不作为当前控制台和后端开发目录。
- 控制台读取的是后端的 REST API，不直接访问 `study`。
- 原始设备 `payload` 在后端不会被改写，后端只会额外返回 `parsed`、`analysis`、`alert_state`。

## 目录说明

```text
yf-monitor/
├─ backend/        Django + DRF 后端
├─ console/        Vue + Element Plus 控制台
└─ study/          资料与 BLE 小程序代码，不动
```

## 推荐阅读顺序

前端开发者建议按这个顺序看：

1. 先读 [backend/README.md](backend/README.md)
2. 再读 [console/README.md](console/README.md)
3. 如果要对接设备协议，再补读 [device-protocol.md](backend/docs/device-protocol.md)

## 一分钟启动

### 1. 启动后端

```powershell
cd G:\bishe\yf-monitor\backend
..\.venv\Scripts\python manage.py runserver
```

如果是第一次启动：

```powershell
cd G:\bishe\yf-monitor\backend
..\.venv\Scripts\python manage.py migrate
..\.venv\Scripts\python manage.py seed_demo_admin
..\.venv\Scripts\python manage.py runserver
```

默认后端地址：

- `http://127.0.0.1:8000`
- API 根路径：`http://127.0.0.1:8000/api/v1`

### 2. 启动控制台

```powershell
cd G:\bishe\yf-monitor\console
npm install
Copy-Item .env.example .env
npm run dev
```

默认控制台地址：

- `http://127.0.0.1:5173`

默认演示账号：

- 用户名：`admin`
- 密码：`admin123456`

## 控制台当前页面

- `/login`：登录页
- `/accounts`：账号管理页，查看账号并创建账号
- `/dashboard`：总览页，展示设备数、测量数、告警数、风险分布、最新事件
- `/devices`：设备列表与设备绑定
- `/measurements`：测量列表，查看结构化结果和原始包
- `/alerts`：告警列表，支持标记已读

## 后端当前 API

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/users`
- `POST /api/v1/auth/users`
- `GET /api/v1/dashboard/overview`
- `GET /api/v1/devices/`
- `POST /api/v1/devices/bind`
- `GET /api/v1/devices/{device_id}/status`
- `POST /api/v1/packets`
- `GET /api/v1/measurements`
- `GET /api/v1/measurements/latest`
- `GET /api/v1/alerts`
- `POST /api/v1/alerts/{id}/read`

## 前端开发协作建议

- 如果你要做“控制台页面开发”，主要看 [console/README.md](console/README.md)
- 如果你要做“App / H5 / 小程序接口对接”，主要看 [backend/README.md](backend/README.md)
- 如果你要做“设备数据解析展示”，要同时看 [backend/README.md](backend/README.md) 和 [device-protocol.md](backend/docs/device-protocol.md)

## 当前已验证

- `backend`: `manage.py check`
- `backend`: `manage.py test`
- `console`: `npm run build`

## 当前限制

- `console` 主要是后台管理和演示面板，不是患者端产品 UI
- 前端未做实时轮询和 WebSocket 推送
- `POST /api/v1/packets` 目前默认是单条上报，不是批量上传接口
- 设备协议解析范围目前只覆盖仓库内已知命令
