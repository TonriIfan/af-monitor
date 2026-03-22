# YF Monitor Console

`console` 是这个项目的后台控制台，技术栈为：

- Vue 3
- Vite
- Element Plus
- Pinia
- Vue Router
- Axios

这份 README 是写给前端开发者的，重点是：

1. 这个控制台是干什么的
2. 怎么本地启动
3. 页面结构是什么
4. 前端如何调用后端 API
5. 现在的代码怎么改、怎么扩展

---

## 1. 控制台定位

这个控制台不是患者端产品页面，它是：

- 后端管理面板
- 毕设演示界面
- 协议调试与数据展示界面
- 前后端联调的可视化入口

它负责展示：

- 登录状态
- 设备列表
- 设备绑定
- 风险总览
- 测量记录
- 告警中心

它**不负责**：

- BLE 通信
- 设备直连
- 患者端交互流程

---

## 2. 运行方式

### 2.1 安装依赖

```powershell
cd yf-monitor\console
npm install
```

### 2.2 配置环境变量

```powershell
Copy-Item .env.example .env
```

当前默认配置：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

说明：

- 当前默认直连本机 Django 后端
- 如果你想改成别的后端地址，可以把它改成：

```env
VITE_API_BASE_URL=http://你的后端地址/api/v1
```

### 2.3 启动开发环境

```powershell
npm run dev
```

默认访问地址：

- `http://127.0.0.1:3000`

### 2.4 构建生产包

```powershell
npm run build
```

构建输出目录：

- `console/dist`

---

## 3. 后端前置要求

控制台依赖后端 API，因此必须先启动后端。

推荐启动方式：

```powershell
cd yf-monitor\backend
..\.venv\Scripts\python manage.py migrate
..\.venv\Scripts\python manage.py seed_demo_admin
..\.venv\Scripts\python manage.py runserver
```

默认演示账号：

- 用户名：`admin`
- 密码：`admin123456`

如果后端没启动，控制台会出现这些问题：

- 登录失败
- 设备列表为空且请求报错
- 总览页数据无法加载
- 告警页、测量页无法返回数据

---

## 4. 页面结构

### 4.1 路由

当前路由在 [router/index.ts](console/src/router/index.ts)

| 路由 | 页面 | 用途 |
| --- | --- | --- |
| `/login` | 登录页 | 登录获取 token |
| `/accounts` | 账号页 | 管理员查看账号、创建账号、切换账号视角 |
| `/dashboard` | 总览页 | 看统计、风险分布、最新测量、最新告警 |
| `/devices` | 设备页 | 看设备清单、绑定设备 |
| `/measurements` | 测量页 | 看测量记录、解析结果、原始包 |
| `/alerts` | 告警页 | 看告警、标记已读 |

### 4.2 布局

控制台布局文件：

- [ConsoleLayout.vue](console/src/layouts/ConsoleLayout.vue)

布局包含：

- 左侧导航
- 顶部标题栏
- 主内容区域

### 4.3 页面文件

| 页面 | 文件 |
| --- | --- |
| 登录 | [LoginView.vue](console/src/views/LoginView.vue) |
| 总览 | [DashboardView.vue](console/src/views/DashboardView.vue) |
| 设备 | [DevicesView.vue](console/src/views/DevicesView.vue) |
| 测量 | [MeasurementsView.vue](console/src/views/MeasurementsView.vue) |
| 告警 | [AlertsView.vue](console/src/views/AlertsView.vue) |

---

## 5. 项目结构

```text
console/
├─ public/
├─ src/
│  ├─ components/      通用组件
│  ├─ layouts/         布局
│  ├─ router/          路由
│  ├─ stores/          Pinia 状态管理
│  ├─ utils/           Axios、格式化工具
│  ├─ views/           页面
│  ├─ App.vue
│  ├─ main.ts
│  └─ styles.css
├─ .env.example
├─ index.html
├─ package.json
└─ vite.config.ts
```

### 5.1 关键文件说明

| 文件 | 作用 |
| --- | --- |
| [main.ts](console/src/main.ts) | 应用入口，注册路由、Pinia、Element Plus |
| [App.vue](console/src/App.vue) | 根组件 |
| [router/index.ts](console/src/router/index.ts) | 路由与登录守卫 |
| [stores/auth.ts](console/src/stores/auth.ts) | 登录状态与 token 存储 |
| [utils/api.ts](console/src/utils/api.ts) | Axios 实例和 token 注入 |
| [utils/format.ts](console/src/utils/format.ts) | 时间和风险字段格式化 |
| [styles.css](console/src/styles.css) | 全局视觉系统与页面样式 |

---

## 6. 登录与鉴权

控制台使用后端的 Token 登录。

流程：

1. 在登录页输入用户名密码
2. 调用 `POST /api/v1/auth/login`
3. 获取 token
4. 存入 `localStorage`
5. 后续请求统一自动带 `Authorization: Token ...`

### 6.1 token 存储位置

`localStorage` key：

- `yf-console-token`
- `yf-console-user`

具体代码在：

- [auth.ts](console/src/stores/auth.ts)
- [management.ts](console/src/stores/management.ts)

### 6.2 Axios 自动注入 token

代码位置：

- [api.ts](console/src/utils/api.ts)

核心逻辑：

```ts
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('yf-console-token')
  if (token) {
    config.headers.Authorization = `Token ${token}`
  }
  return config
})
```

### 6.3 路由守卫

未登录访问业务页面会自动跳到 `/login`。

逻辑在：

- [router/index.ts](console/src/router/index.ts)

---

## 7. 控制台与 API 的对应关系

### 7.1 登录页

页面：

- [LoginView.vue](console/src/views/LoginView.vue)

调用接口：

- `POST /api/v1/auth/login`

作用：

- 获取 token
- 获取用户基本信息
- 跳转到总览页

### 7.2 总览页

页面：

- [DashboardView.vue](console/src/views/DashboardView.vue)

调用接口：

- `GET /api/v1/dashboard/overview`

展示内容：

- 设备数
- 测量数
- 告警数
- 未读告警数
- 风险等级分布
- 最新测量
- 最新告警

### 7.3 设备页

页面：

- [DevicesView.vue](console/src/views/DevicesView.vue)

调用接口：

- `GET /api/v1/devices/`
- `POST /api/v1/devices/bind`

展示内容：

- 已绑定设备列表
- 设备别名
- 最近测量时间
- 未读告警数

### 7.4 测量页

页面：

- [MeasurementsView.vue](console/src/views/MeasurementsView.vue)

调用接口：

- `GET /api/v1/measurements`

展示内容：

- 设备 ID
- 测量类型
- 风险等级
- 解析结果 `parsed`
- 原始包 `raw_payload.payload`
- 时间

### 7.5 告警页

页面：

- [AlertsView.vue](console/src/views/AlertsView.vue)

调用接口：

- `GET /api/v1/alerts`
- `POST /api/v1/alerts/{id}/read`

展示内容：

- 告警标题
- 告警等级
- 规则命中
- 时间
- 已读/未读状态

### 7.6 账号页

页面：

- [AccountsView.vue](console/src/views/AccountsView.vue)

调用接口：

- `GET /api/v1/auth/users`
- `POST /api/v1/auth/users`

展示内容：

- 所有账号的设备数、测量数、告警数
- 账号角色
- 最近活动时间
- 创建新账号
- 一键切换“当前查看账号”

---

## 8. 前端开发时最需要知道的后端字段

### 8.1 `measurement` 结构

当前控制台拿到的单条测量对象核心结构：

```json
{
  "id": 12,
  "device_id": "ring-001",
  "measured_at": "2026-03-15T14:30:00+08:00",
  "packet_kind": "heart_rate",
  "raw_payload": {
    "device_id": "ring-001",
    "client_time": "2026-03-15T14:30:00+08:00",
    "source": "wechat-miniapp",
    "payload": {
      "frame_hex": "00 00 31 00 03 78 28 55 8E 0E"
    }
  },
  "parsed": {
    "wearStatusText": "采集中",
    "heartRate": 120,
    "hrv": 40,
    "stress": 85,
    "temperature": 37.26
  },
  "analysis": {
    "algorithm_version": "rules-v1",
    "risk_level": "high",
    "risk_score": 0.65,
    "labels": ["较高异常心律风险"],
    "triggers": ["tachycardia", "hrv_instability", "high_stress"],
    "summary": "命中规则: tachycardia, hrv_instability, high_stress。",
    "should_alert": true
  },
  "alert_state": {
    "has_alert": true,
    "latest_alert_id": 1,
    "level": "high",
    "status": "unread"
  }
}
```

### 8.2 前端推荐展示层级

如果你是后续来做更多页面，建议按这个层级组织 UI：

- 第一层：`device_id`、`packet_kind`、`measured_at`
- 第二层：`parsed`
- 第三层：`analysis.risk_level`、`analysis.summary`
- 第四层：`raw_payload.payload`

原因：

- 第一层适合列表页摘要
- 第二层适合业务数据展示
- 第三层适合风险标签和告警入口
- 第四层适合调试和排错

---

## 9. 风险等级前端映射建议

当前代码已经在 [format.ts](console/src/utils/format.ts) 里提供了基础映射。

### 9.1 文案映射

| 后端值 | 前端文案 |
| --- | --- |
| `low` | 低风险 |
| `moderate` | 中风险 |
| `high` | 高风险 |
| `critical` | 极高风险 |
| `unknown` | 未知 |

### 9.2 颜色映射建议

| 后端值 | 标签颜色 |
| --- | --- |
| `low` | success |
| `moderate` | warning |
| `high` | danger |
| `critical` | danger |
| `unknown` | info |

---

## 10. 新页面如何接入

如果你要新增一个业务页面，推荐步骤：

1. 在 `src/views/` 下新建页面
2. 在 `src/router/index.ts` 增加路由
3. 如果需要共享状态，再考虑加到 `stores/`
4. 所有 API 调用统一走 `utils/api.ts`
5. 通用格式处理统一放 `utils/format.ts`

### 10.1 新增一个页面的最小示例

```vue
<template>
  <div class="page-grid">
    <article class="panel">
      <div class="panel__header">
        <div>
          <p class="section-eyebrow">Example</p>
          <h3>示例页面</h3>
        </div>
      </div>
      <p>这里写你的页面内容。</p>
    </article>
  </div>
</template>

<script setup lang="ts">
</script>
```

然后在路由里加：

```ts
{
  path: 'example',
  name: 'example',
  component: () => import('../views/ExampleView.vue'),
}
```

---

## 11. 常见开发问题

### 11.1 登录失败

先检查：

- 后端是否启动
- `admin` 用户是否存在
- token 接口路径是否正确

建议直接执行：

```powershell
cd yf-monitor\backend
..\.venv\Scripts\python manage.py seed_demo_admin
```

### 11.2 页面空白但不报错

先检查：

- 浏览器控制台是否有 API 404/401
- `.env` 是否配置正确
- Vite 代理是否生效

### 11.3 401 未授权

一般是：

- token 没存进去
- token 被清空
- Axios 请求头没带 `Authorization`

### 11.4 设备页没有数据

这是正常的，说明还没有绑定设备。

先在设备页绑定一个设备，或者先通过 API 写入绑定关系。

---

## 12. 当前限制

- 没有分页
- 没有实时推送
- 没有图表库，风险分布目前用轻量条形展示
- Element Plus 打包后主 chunk 仍然偏大，但 `build` 已通过
- 登录页默认预填的是演示账号，不代表生产账号策略

---

## 13. 推荐配套阅读

- [backend/README.md](backend/README.md)
- [device-protocol.md](backend/docs/device-protocol.md)

如果你是前端同学，最实用的阅读顺序是：

1. 先看本文件，知道控制台怎么跑
2. 再看 [backend/README.md](backend/README.md)，知道 API 细节
3. 最后看 [device-protocol.md](backend/docs/device-protocol.md)，了解 `parsed` 字段来源
