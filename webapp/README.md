# webapp · 心脏卫士用户端

面向普通用户的 Web 端，基于 Vue 3 + Element Plus + Web Bluetooth API。
与 `console/`（管理员端）并列，公用同一套后端 `/api/v1`。

## 主要功能

- 登录 / 退出（走 `POST /api/v1/auth/login`）
- 设备绑定、解绑、当前绑定查看
- **使用 Web Bluetooth API 直接连接智能戒指**，订阅 notify 帧
- 每一帧按原始 hex 上报到后端 `POST /api/v1/packets`（节流 800ms）
- 实时心率 / 风险等级 / 历史趋势图 / 告警查看

## 浏览器要求

Web Bluetooth API 为实验性能力，目前仅在基于 Blink 内核的浏览器中可用：

| 浏览器 | 桌面 | 移动 |
|--------|------|------|
| Chrome | ✅ | ✅（Android） |
| Edge | ✅ | ✅（Android） |
| Opera | ✅ | ✅（Android） |
| Safari | ❌ | ❌（iOS） |
| Firefox | ❌ | ❌ |

同时必须满足"安全上下文"：HTTPS 或 `localhost`，且 `requestDevice` 必须由真实用户手势触发。

## 启动

```powershell
cd webapp
npm install
Copy-Item .env.example .env
npm run dev
```

默认：

- Web 地址：<http://127.0.0.1:3001>
- API 地址：通过 Vite 代理转到 `http://127.0.0.1:8000`（与后端 `manage.py runserver` 默认地址一致）

## 构建

```powershell
npm run build
npm run preview
```

`npm run build` 会先跑 `vue-tsc --noEmit` 做严格类型检查，再用 Vite 构建生产资源。

## 与 console 的关系

| 目标 | console | webapp |
|------|---------|--------|
| 受众 | 管理员 / 运营 | 普通用户 / 患者 |
| 登录接口 | `/auth/console-login`（仅管理员） | `/auth/login`（任意账号） |
| Token 存储 | `yf-console-token` | `yf-webapp-token` |
| Web Bluetooth | 不使用 | 核心依赖 |
| UI 风格 | 桌面侧栏 | 移动底部 Tab Bar |

两端代码互不依赖，可以独立部署到不同子域（例如
`console.heartguard.cn` 与 `app.heartguard.cn`）。

## 目录结构

```text
webapp/
├─ index.html
├─ vite.config.ts
├─ tsconfig.json
├─ package.json
├─ public/                 # 静态资源
└─ src/
   ├─ main.ts
   ├─ App.vue
   ├─ styles.css
   ├─ env.d.ts
   ├─ router/
   │  └─ index.ts
   ├─ stores/
   │  ├─ index.ts
   │  ├─ auth.ts           # 登录态，独立于 console
   │  └─ ble.ts            # BLE 状态、帧日志、上报节流
   ├─ utils/
   │  ├─ api.ts            # axios + Token 拦截器
   │  ├─ format.ts         # 时间 / 风险等级 / hex 工具
   │  └─ ble.ts            # Web Bluetooth 封装（单例 RingBleClient）
   ├─ layouts/
   │  └─ AppLayout.vue     # 带底部 Tab Bar 的外壳
   └─ views/
      ├─ LoginView.vue
      ├─ HomeView.vue
      ├─ DeviceView.vue
      ├─ MeasurementsView.vue
      ├─ AlertsView.vue
      └─ ProfileView.vue
```

## Web Bluetooth 连接流程

```
用户点击"连接戒指"
        ↓
navigator.bluetooth.requestDevice({ acceptAllDevices, optionalServices })
        ↓（浏览器原生弹窗，用户手动选设备）
device.gatt.connect()
        ↓
service = getPrimaryService('bae80001-...')
writeChar = service.getCharacteristic('bae80010-...')
notifyChar = service.getCharacteristic('bae80011-...')
        ↓
notifyChar.startNotifications()
        ↓
每次 characteristicvaluechanged 事件：
  → 推送到 stores/ble.ts 的日志
  → 节流 800ms 后 POST /api/v1/packets
```

## 风险与边界

- iOS Safari 和 Firefox 不支持，iOS 用户需走 App 同学的 Android/iOS 端
- 浏览器切后台时 BLE 可能断开，`gattserverdisconnected` 事件会把状态置为 `disconnected`
- 设备首次连接需要手动从浏览器弹窗选设备；无法做自动重连（浏览器安全限制）
- 与 App 端上报走同一个 `/api/v1/packets`，后端做了按 `source='web-bluetooth'` 的区分但不影响分析
