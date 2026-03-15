# YF Monitor Backend

`backend` 是智能房颤监测项目的一期后端。

它的职责不是做 BLE 通信，而是接收上报后的设备数据，并完成：

- 用户认证
- 设备绑定
- 原始包入库
- 协议解析
- 规则版风险分析
- 历史测量查询
- 告警查询与已读处理
- 为控制台和未来 App 提供统一 REST API


1. API 怎么登录
2. 每个接口收什么、返回什么
3. 前端应该怎么调用
4. 哪些字段可以直接展示
5. 哪些地方要注意兼容性

---

## 1. 技术栈

- Python 3
- Django 5
- Django REST Framework
- SQLite 默认开发库
- MySQL 作为可切换生产/演示数据库

---

## 2. 运行方式

### 2.1 首次启动

```powershell
python3 -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
cd backend
..\.venv\Scripts\python manage.py migrate
..\.venv\Scripts\python manage.py seed_demo_admin
..\.venv\Scripts\python manage.py runserver
```

说明：

- `seed_demo_admin` 会创建一个演示管理员，便于控制台直接登录。
- 默认管理员账号：
  - 用户名：`admin`
  - 密码：`admin123456`

### 2.2 常用命令

```powershell
cd G:\bishe\yf-monitor\backend
..\.venv\Scripts\python manage.py runserver
..\.venv\Scripts\python manage.py test
..\.venv\Scripts\python manage.py check
..\.venv\Scripts\python manage.py seed_demo_admin
```

---

## 3. 环境变量

参考文件：[.env.example](backend/.env.example)

支持的关键变量：

| 变量名 | 说明 | 默认值 |
| --- | --- | --- |
| `SECRET_KEY` | Django 密钥 | `dev-only-secret-key` |
| `DEBUG` | 是否调试模式 | `true` |
| `ALLOWED_HOSTS` | 允许访问的 host | `127.0.0.1,localhost` |
| `DB_ENGINE` | `sqlite` 或 `mysql` | `sqlite` |
| `DB_NAME` | 数据库名 | `yf_monitor` |
| `DB_USER` | MySQL 用户名 | `root` |
| `DB_PASSWORD` | MySQL 密码 | 空 |
| `DB_HOST` | MySQL 地址 | `127.0.0.1` |
| `DB_PORT` | MySQL 端口 | `3306` |
| `CORS_ALLOWED_ORIGINS` | 允许跨域的前端地址 | `http://localhost:5173,http://127.0.0.1:5173` |

说明：

- 默认本地开发使用 SQLite，不需要额外安装数据库。
- 如果前端运行在 Vite 默认端口 `5173`，后端已经允许跨域。

---

## 4. 数据设计原则

这个项目有一个很重要的约束：

**设备原始 `payload` 不改格式。**

也就是说，前端或采集端传上来的：

```json
{
  "device_id": "ring-001",
  "client_time": "2026-03-15T14:30:00+08:00",
  "source": "wechat-miniapp",
  "payload": {
    "frame_hex": "00 00 31 00 03 48 22 10 0C 34",
    "frame_bytes": [0, 0, 49, 0, 3, 72, 34, 16, 12, 52]
  }
}
```

后端会：

- 原样保留这份原始请求
- 从 `payload` 里解析字段
- 生成 `analysis`
- 生成 `alert_state`

但不会回写修改原始 `payload`

因此你会在查询接口里同时拿到：

- `raw_payload`
- `parsed`
- `analysis`
- `alert_state`

这四层信息对前端开发的意义是：

- `raw_payload`：做原始包调试、协议排错
- `parsed`：做业务展示
- `analysis`：做风险等级和规则命中展示
- `alert_state`：做告警状态展示

---

## 5. 认证方式

认证方式是 `Token Authentication`。

前端调用流程：

1. 调 `POST /api/v1/auth/login`
2. 拿到 `token`
3. 之后在请求头里加：

```http
Authorization: Token <token>
```

### 5.1 登录接口

**请求**

`POST /api/v1/auth/login`

```json
{
  "username": "admin",
  "password": "admin123456"
}
```

**响应**

```json
{
  "token": "8fc4f2...",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com"
  }
}
```

### 5.2 前端 Axios 示例

```ts
import axios from 'axios'

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/api/v1',
})

const loginResp = await api.post('/auth/login', {
  username: 'admin',
  password: 'admin123456',
})

const token = loginResp.data.token

const devicesResp = await api.get('/devices/', {
  headers: {
    Authorization: `Token ${token}`,
  },
})
```

---

## 6. API 总览

当前可用接口如下：

| 方法 | 路径 | 认证 | 用途 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/auth/login` | 否 | 登录获取 token |
| `GET` | `/api/v1/auth/users` | 管理员 | 获取账号列表 |
| `POST` | `/api/v1/auth/users` | 管理员 | 创建账号 |
| `GET` | `/api/v1/dashboard/overview` | 是 | 控制台总览数据 |
| `GET` | `/api/v1/devices/` | 是 | 获取设备列表 |
| `POST` | `/api/v1/devices/bind` | 是 | 绑定新设备 |
| `GET` | `/api/v1/devices/{device_id}/status` | 是 | 获取设备状态 |
| `POST` | `/api/v1/packets` | 否/可带 token | 上报原始设备包 |
| `GET` | `/api/v1/measurements` | 是 | 查询测量列表 |
| `GET` | `/api/v1/measurements/latest` | 是 | 查询最新测量 |
| `GET` | `/api/v1/alerts` | 是 | 查询告警列表 |
| `POST` | `/api/v1/alerts/{id}/read` | 是 | 标记告警已读 |

说明：

- 控制台使用的几乎都是需要 token 的接口。
- `POST /packets` 允许无 token 上报，是为了兼容采集端单独上传。
- 如果采集端没带 token，后端会尝试根据设备当前绑定关系推断用户。
- 管理员可以通过 `user_id` 查询参数切换到指定账号的数据视角。

---

## 7. 详细 API 说明

### 7.0 获取账号列表

**请求**

`GET /api/v1/auth/users`

仅管理员可访问。

**响应**

```json
[
  {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "first_name": "",
    "last_name": "",
    "is_active": true,
    "is_staff": true,
    "is_superuser": true,
    "device_count": 2,
    "measurement_count": 24,
    "alert_count": 3,
    "unread_alert_count": 1,
    "latest_activity_at": "2026-03-15T15:10:00+08:00",
    "date_joined": "2026-03-15T14:00:00+08:00"
  }
]
```

### 7.0.1 创建账号

**请求**

`POST /api/v1/auth/users`

```json
{
  "username": "patient-a",
  "password": "pass12345",
  "email": "patient-a@example.com",
  "first_name": "Patient",
  "last_name": "A",
  "is_staff": false,
  "is_active": true
}
```

仅管理员可访问。返回创建后的账号摘要对象。

### 7.1 获取总览

**请求**

`GET /api/v1/dashboard/overview`

请求头：

```http
Authorization: Token <token>
```

管理员额外支持：

- 不传 `user_id`：查看所有账号总览
- 传 `user_id`：查看指定账号总览

**响应**

```json
{
  "counts": {
    "devices": 1,
    "measurements": 12,
    "alerts": 3,
    "unread_alerts": 2
  },
  "risk_distribution": [
    {
      "risk_level": "high",
      "total": 2
    },
    {
      "risk_level": "low",
      "total": 10
    }
  ],
  "latest_measurements": [
    {
      "id": 12,
      "device_id": "ring-001",
      "measured_at": "2026-03-15T14:31:00+08:00",
      "packet_kind": "heart_rate",
      "parsed": {
        "wearStatusText": "采集中",
        "heartRate": 120,
        "hrv": 40,
        "stress": 85,
        "temperature": 37.26
      },
      "risk_level": "high"
    }
  ],
  "latest_alerts": [
    {
      "id": 1,
      "device_id": "ring-001",
      "level": "high",
      "title": "疑似房颤风险预警",
      "status": "unread",
      "created_at": "2026-03-15T14:31:00+08:00"
    }
  ]
}
```

前端用途：

- 首页统计卡片
- 风险分布条形可视化
- 最新测量与最新告警摘要

---

### 7.2 获取设备列表

**请求**

`GET /api/v1/devices/`

**响应**

```json
[
  {
    "device_id": "ring-001",
    "name": "Smart Ring",
    "device_type": "smart-ring",
    "source": "wechat-miniapp",
    "last_seen_at": "2026-03-15T15:05:00+08:00",
    "alias": "我的戒指",
    "unread_alerts": 2,
    "latest_measurement_at": "2026-03-15T14:31:00+08:00"
  }
]
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `device_id` | 设备唯一 ID |
| `name` | 设备名称 |
| `device_type` | 当前固定为 `smart-ring` |
| `source` | 设备来源，默认 `wechat-miniapp` |
| `last_seen_at` | 最近被后端看到的时间 |
| `alias` | 当前用户给这个设备设置的别名 |
| `unread_alerts` | 当前设备未读告警数 |
| `latest_measurement_at` | 最近一条测量时间 |

---

### 7.3 绑定设备

**请求**

`POST /api/v1/devices/bind`

```json
{
  "device_id": "ring-001",
  "name": "Smart Ring",
  "alias": "我的戒指",
  "source": "wechat-miniapp"
}
```

**响应**

```json
{
  "id": 1,
  "device_id": "ring-001",
  "device_name": "Smart Ring",
  "alias": "我的戒指",
  "is_active": true,
  "bound_at": "2026-03-15T15:00:00+08:00"
}
```

注意：

- 一个设备同一时间只允许一个有效绑定。
- 如果设备已绑定给其他用户，新的绑定会把旧绑定置为无效。

---

### 7.4 获取设备状态

**请求**

`GET /api/v1/devices/ring-001/status`

**响应**

```json
{
  "device_id": "ring-001",
  "name": "Smart Ring",
  "source": "wechat-miniapp",
  "last_seen_at": "2026-03-15T15:05:00+08:00",
  "unread_alerts": 2,
  "latest_measurement": {
    "id": 12,
    "measured_at": "2026-03-15T14:31:00+08:00",
    "packet_kind": "heart_rate",
    "parsed": {
      "wearStatusText": "采集中",
      "heartRate": 120,
      "hrv": 40,
      "stress": 85,
      "temperature": 37.26
    },
    "analysis": {
      "risk_level": "high",
      "risk_score": 0.65,
      "summary": "命中规则: tachycardia, hrv_instability, high_stress。"
    }
  }
}
```

前端用途：

- 设备详情页
- 设备状态卡片
- 当前风险快照

---

### 7.5 上报原始包

**请求**

`POST /api/v1/packets`

```json
{
  "device_id": "ring-001",
  "client_time": "2026-03-15T14:30:00+08:00",
  "source": "wechat-miniapp",
  "payload": {
    "frame_hex": "00 00 31 00 03 78 28 55 8E 0E",
    "frame_bytes": [0, 0, 49, 0, 3, 120, 40, 85, 142, 14]
  }
}
```

可选字段：

- `session_key`

```json
{
  "device_id": "ring-001",
  "client_time": "2026-03-15T14:30:00+08:00",
  "source": "wechat-miniapp",
  "session_key": "session-20260315-01",
  "payload": {
    "frame_hex": "00 00 31 00 03 78 28 55 8E 0E"
  }
}
```

**响应**

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
      "frame_hex": "00 00 31 00 03 78 28 55 8E 0E",
      "frame_bytes": [0, 0, 49, 0, 3, 120, 40, 85, 142, 14]
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

注意：

- `payload` 内原始协议字段不变
- 你可以只传 `frame_hex` 或只传 `frame_bytes`
- 后端会自动补足另一种表示并入库
- 未识别的命令也会保留原始包，只是 `parsed` 可能为空

---

### 7.6 查询测量列表

**请求**

`GET /api/v1/measurements`

支持查询参数：

| 参数 | 说明 |
| --- | --- |
| `device_id` | 按设备过滤 |
| `start` | 起始时间，ISO 格式 |
| `end` | 结束时间，ISO 格式 |

示例：

```http
GET /api/v1/measurements?device_id=ring-001
GET /api/v1/measurements?start=2026-03-15T00:00:00+08:00&end=2026-03-15T23:59:59+08:00
```

**响应**

数组元素结构与 `POST /packets` 的响应结构一致：

- `id`
- `device_id`
- `measured_at`
- `packet_kind`
- `raw_payload`
- `parsed`
- `analysis`
- `alert_state`

前端用途：

- 测量历史列表
- 协议调试页
- 风险记录页

---

### 7.7 查询最新测量

**请求**

`GET /api/v1/measurements/latest`

可选参数：

- `device_id`

**响应**

结构与单条 `measurement` 一致。

当没有数据时：

```json
{
  "detail": "暂无测量数据。"
}
```

状态码：

- `404`

---

### 7.8 查询告警列表

**请求**

`GET /api/v1/alerts`

可选参数：

- `device_id`

**响应**

```json
[
  {
    "id": 1,
    "device_id": "ring-001",
    "measurement_id": 12,
    "level": "high",
    "title": "疑似房颤风险预警",
    "message": "命中规则: tachycardia, hrv_instability, high_stress。",
    "trigger_codes": ["tachycardia", "hrv_instability", "high_stress"],
    "status": "unread",
    "is_read": false,
    "read_at": null,
    "created_at": "2026-03-15T14:31:00+08:00"
  }
]
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `level` | `low` / `moderate` / `high` / `critical` |
| `status` | `unread` / `read` |
| `is_read` | 前端可直接用布尔值判断 UI 状态 |
| `trigger_codes` | 命中的规则列表 |

---

### 7.9 标记告警已读

**请求**

`POST /api/v1/alerts/1/read`

请求体可以为空：

```json
{}
```

**响应**

返回更新后的整条告警对象。

```json
{
  "id": 1,
  "device_id": "ring-001",
  "measurement_id": 12,
  "level": "high",
  "title": "疑似房颤风险预警",
  "message": "命中规则: tachycardia, hrv_instability, high_stress。",
  "trigger_codes": ["tachycardia", "hrv_instability", "high_stress"],
  "status": "read",
  "is_read": true,
  "read_at": "2026-03-15T15:10:00+08:00",
  "created_at": "2026-03-15T14:31:00+08:00"
}
```

---

## 8. `parsed` 字段说明

`parsed` 的字段命名优先保持和现有 BLE 小程序页面解析逻辑一致。

已知字段包括：

| 字段 | 含义 |
| --- | --- |
| `batteryLevel` | 电量 |
| `batteryState` | 电池状态 |
| `isSyncTime` | 时间同步结果 |
| `ringTime` | 设备时间 |
| `timezone` | 时区字节 |
| `wearStatusText` | 心率测量佩戴状态 |
| `heartRate` | 心率 |
| `hrv` | HRV |
| `stress` | 压力值 |
| `temperature` | 体温或温度值 |
| `oxygenWearStatusText` | 血氧测量佩戴状态 |
| `oxygenHeartRate` | 血氧测量时的心率 |
| `oxygen` | 血氧 |
| `oxygenTemperature` | 血氧测量温度 |
| `StatusText` | 体温测量状态 |
| `TempTest` | 体温测量值 |

具体协议可看 [device-protocol.md](backend/docs/device-protocol.md)

---

## 9. `analysis` 字段说明

后端当前使用规则版分析器，不是医学诊断模型。

`analysis` 结构如下：

```json
{
  "algorithm_version": "rules-v1",
  "risk_level": "high",
  "risk_score": 0.65,
  "labels": ["较高异常心律风险"],
  "triggers": ["tachycardia", "hrv_instability", "high_stress"],
  "summary": "命中规则: tachycardia, hrv_instability, high_stress。",
  "should_alert": true
}
```

### 当前规则示例

- `heartRate > 110`：`tachycardia`
- `heartRate < 50`：`bradycardia`
- `hrv >= 35`：`hrv_instability`
- `stress >= 80`：`high_stress`
- `oxygen < 95`：`low_oxygen`
- 温度过高：`fever`

前端建议：

- `risk_level` 用于颜色映射
- `risk_score` 用于进度条或强度显示
- `triggers` 直接做标签列表
- `summary` 直接做说明文本

---

## 10. 错误返回约定

项目基于 DRF，常见错误格式如下。

### 10.1 字段校验错误

```json
{
  "payload": ["payload 至少需要 frame_hex 或 frame_bytes。"]
}
```

### 10.2 权限错误

```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 10.3 资源不存在

```json
{
  "detail": "Not found."
}
```

前端建议：

- 先优先显示 `detail`
- 如果没有 `detail`，再按字段错误逐项展示

---

## 11. 前端联调建议

### 11.1 推荐联调顺序

1. 先跑通登录
2. 跑设备列表和设备绑定
3. 用 `POST /packets` 人工塞一条测试数据
4. 看 `/dashboard/overview`
5. 看 `/measurements`
6. 看 `/alerts`

### 11.2 最小联调脚本

```ts
import axios from 'axios'

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/api/v1',
})

async function demo() {
  const login = await api.post('/auth/login', {
    username: 'admin',
    password: 'admin123456',
  })

  const token = login.data.token

  const authHeaders = {
    Authorization: `Token ${token}`,
  }

  await api.post(
    '/devices/bind',
    {
      device_id: 'ring-001',
      name: 'Smart Ring',
      alias: '测试戒指',
    },
    { headers: authHeaders },
  )

  await api.post('/packets', {
    device_id: 'ring-001',
    client_time: '2026-03-15T14:30:00+08:00',
    source: 'wechat-miniapp',
    payload: {
      frame_hex: '00 00 31 00 03 78 28 55 8E 0E',
    },
  })

  const dashboard = await api.get('/dashboard/overview', { headers: authHeaders })
  console.log(dashboard.data)
}
```

---

## 12. 当前限制

- 没有分页接口，当前列表接口默认直接返回全量结果
- 没有 WebSocket 实时推送
- 没有批量上传接口
- 没有为移动端单独设计字段格式，当前强调“统一接口”
- 风险分析是规则版，不是训练模型结果

---

## 13. 相关文件

- [settings.py](backend/config/settings.py)
- [devices/views.py](backend/devices/views.py)
- [monitoring/views.py](backend/monitoring/views.py)
- [monitoring/services.py](backend/monitoring/services.py)
- [device-protocol.md](backend/docs/device-protocol.md)
