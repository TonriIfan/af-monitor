# HeartGuard 前端接口对接手册

## 1. 文档目标

这份文档给前端开发者直接使用，目标是把当前后端可用接口说明清楚：

- 接口地址怎么拼
- 登录和 Token 怎么带
- 管理员和普通用户有什么差别
- 每个接口收什么、回什么
- 哪些字段适合直接展示
- 哪些接口支持按 `user_id` 切换视角

当前后端接口仍使用：

- `/api/v1/...`

所以即使生产环境 API 域名已经规划为：

- `https://api.heartguard.cn`

当前完整地址仍然是：

- `https://api.heartguard.cn/api/v1/...`

例如：

- `https://api.heartguard.cn/api/v1/measurements`

## 2. 基础信息

### 2.1 开发环境 Base URL

本地开发时：

```text
http://127.0.0.1:8000/api/v1
```

### 2.2 生产环境 Base URL

线上建议：

```text
https://api.heartguard.cn/api/v1
```

### 2.3 当前接口分组

- 认证与账号：`/auth/...`
- 设备：`/devices/...`
- 监测与分析：`/packets`、`/measurements`、`/alerts`
- 管理总览：`/dashboard/overview`
- AI：`/ai/settings`、`/measurements/{id}/llm-insight`

## 3. 鉴权方式

当前后端使用：

- `Token Authentication`

登录成功后会返回：

```json
{
  "token": "xxxx",
  "user": {
    "id": 1,
    "username": "admin",
    "role": "admin"
  }
}
```

后续请求都带：

```http
Authorization: Token <token>
```

### 3.1 Axios 推荐写法

```ts
import axios from 'axios'

export const api = axios.create({
  baseURL: 'https://api.heartguard.cn/api/v1',
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Token ${token}`
  }
  return config
})
```

### 3.2 401 的含义

如果接口返回 `401 Unauthorized`，通常表示：

- 没带 Token
- Token 已失效
- 本地缓存的是旧 Token

这不是参数错误，而是登录态问题。

## 4. 角色与数据视角

当前系统有两种用户角色：

- `admin`
- `user`

### 4.1 普通用户

普通用户调用查询接口时，只能看到自己绑定设备下的数据。

### 4.2 管理员

管理员默认看到的是：

- 全部普通用户的数据

管理员还可以通过传 `user_id` 切换到某个具体用户视角。

支持 `user_id` 的常见接口有：

- `GET /devices/?user_id=2`
- `GET /measurements?user_id=2`
- `GET /measurements/latest?user_id=2`
- `GET /alerts?user_id=2`
- `GET /dashboard/overview?user_id=2`
- `GET /measurements/trends?user_id=2`
- `GET /devices/{device_id}/status?user_id=2`

部分 `POST` 接口也支持从 body 里传 `user_id`，例如：

- `POST /devices/bind`

## 5. 返回结构设计原则

监测类接口会同时返回四层信息：

- `raw_payload`
- `parsed`
- `analysis`
- `alert_state`

含义如下：

### 5.1 `raw_payload`

原始上报内容，后端不会修改原始 `payload` 结构。

适合：

- 协议排错
- 调试 BLE 上报
- 和小程序原始数据做对照

### 5.2 `parsed`

后端根据设备协议解析出的结构化字段。

适合：

- 页面展示
- 图表绘制
- 业务逻辑判断

### 5.3 `analysis`

后端分析算法输出。

当前算法版本：

- `rules-window-baseline-v2`

适合：

- 风险颜色
- 风险等级文案
- 触发原因展示
- AI 解读上下文

### 5.4 `alert_state`

当前这条测量关联的最新告警状态。

适合：

- 列表中标记是否告警
- 点击跳转到告警详情

## 6. 账号与认证接口

---

### 6.1 普通登录

**接口**

`POST /auth/login`

**用途**

- 普通登录
- 未来 App、小程序、非控制台前端可使用

**是否需要鉴权**

- 否

**请求体**

```json
{
  "username": "patient001",
  "password": "demo12345",
  "login_context": {
    "ip": "39.224.1.135",
    "city": "北京市",
    "region": "北京市",
    "country_name": "China",
    "latitude": 39.9042,
    "longitude": 116.4074
  }
}
```

`login_context` 可选，建议 Web 前端登录时传。

它的作用是：

- 记录登录 IP
- 记录地理位置
- 给后续账号总览和健康分析做辅助特征

**成功响应**

```json
{
  "token": "xxxxxxxx",
  "user": {
    "id": 12,
    "username": "patient001",
    "email": "patient001@demo.local",
    "first_name": "娜敏",
    "last_name": "刘",
    "role": "user",
    "is_staff": false,
    "is_superuser": false,
    "last_login_ip": "39.224.1.135",
    "last_login_location": {
      "country": "China",
      "region": "北京市",
      "city": "北京市",
      "latitude": 39.9042,
      "longitude": 116.4074
    }
  }
}
```

**失败响应**

```json
{
  "non_field_errors": [
    "用户名或密码错误。"
  ]
}
```

或：

```json
{
  "detail": "用户名或密码错误。"
}
```

前端应兼容这两种 DRF 风格错误。

---

### 6.2 控制台登录

**接口**

`POST /auth/console-login`

**用途**

- 仅管理控制台使用
- 只允许管理员登录

**是否需要鉴权**

- 否

**请求体**

和普通登录相同。

```json
{
  "username": "admin",
  "password": "admin123456",
  "login_context": {
    "ip": "219.129.125.196",
    "city": "南京市",
    "region": "江苏省",
    "country_name": "China",
    "latitude": 32.0603,
    "longitude": 118.7969
  }
}
```

**成功响应**

和普通登录相同。

**失败响应**

当账号不是管理员时：

```json
{
  "detail": "只有管理员账号可以登录控制台。"
}
```

---

### 6.3 App 用户注册

**接口**

`POST /auth/register`

**用途**

- 给 App 或普通用户端提供公共注册能力
- 只能注册普通用户
- 不允许通过该接口创建管理员

**是否需要鉴权**

- 否

**请求体**

```json
{
  "username": "patient-mobile-001",
  "password": "demo12345",
  "email": "patient001@example.com",
  "first_name": "芳婷",
  "last_name": "陈",
  "login_context": {
    "ip": "202.96.64.68",
    "city": "广州市",
    "region": "广东省",
    "country_name": "China",
    "latitude": 23.1291,
    "longitude": 113.2644
  },
  "profile": {
    "phone": "13800138000",
    "age": 61,
    "sex": "female",
    "notes": "有心悸史"
  }
}
```

**字段说明**

- `username`
  - 必填，唯一
- `password`
  - 必填，最少 8 位
- `email`
  - 可选
- `first_name` / `last_name`
  - 可选
- `login_context`
  - 可选
  - 若前端能拿到公网 IP 与地理位置，建议直接带上
- `profile`
  - 可选
  - 当前支持：
  - `phone`
  - `age`
  - `sex`
  - `notes`

**成功响应**

```json
{
  "token": "xxxxxxxx",
  "user": {
    "id": 25,
    "username": "patient-mobile-001",
    "email": "patient001@example.com",
    "first_name": "芳婷",
    "last_name": "陈",
    "role": "user",
    "is_staff": false,
    "is_superuser": false,
    "last_login_ip": "202.96.64.68",
    "last_login_location": {
      "country": "China",
      "region": "广东省",
      "city": "广州市",
      "latitude": 23.1291,
      "longitude": 113.2644
    }
  }
}
```

**前端注意**

- 注册成功后后端会直接返回 Token
- 一般不需要再紧接着调用一次登录接口
- 当前注册出来的账号固定是 `role = user`

---

### 6.4 获取账号列表

**接口**

`GET /auth/users`

**用途**

- 管理员查看全部账号
- 账号管理页列表

**是否需要鉴权**

- 是，且必须是管理员

**查询参数**

- 无

**成功响应**

```json
[
  {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "first_name": "",
    "last_name": "",
    "role": "admin",
    "is_active": true,
    "is_staff": true,
    "is_superuser": false,
    "last_login_ip": "127.0.0.1",
    "last_login_location": {
      "country": "",
      "region": "",
      "city": "",
      "latitude": null,
      "longitude": null
    },
    "device_count": 0,
    "measurement_count": 0,
    "alert_count": 0,
    "unread_alert_count": 0,
    "latest_activity_at": null,
    "date_joined": "2026-03-16T01:00:00+08:00"
  }
]
```

**字段说明**

- `first_name` / `last_name`
  - 前端若显示中文姓名，建议用：
  - `last_name + first_name`
- `last_login_location.region`
  - 省级行政区
- `last_login_location.city`
  - 城市
- `device_count`
  - 当前活跃绑定设备数
- `measurement_count`
  - 用户名下测量总数
- `unread_alert_count`
  - 未读告警数
- `latest_activity_at`
  - 最近测量时间，不是登录时间

---

### 6.5 创建单个账号

**接口**

`POST /auth/users`

**用途**

- 管理员手工创建账号

**是否需要鉴权**

- 是，且必须是管理员

**请求体**

```json
{
  "username": "patient011",
  "password": "demo12345",
  "email": "patient011@demo.local",
  "first_name": "芳婷",
  "last_name": "陈",
  "role": "user",
  "is_active": true,
  "generate_china_location": true
}
```

**字段说明**

- `password`
  - 最少 8 位
- `role`
  - `admin` 或 `user`
- `generate_china_location`
  - 为演示环境自动生成中国公网 IP 和省市位置
- `login_context`
  - 如果你想自己指定地理信息，也可以传

例如：

```json
{
  "username": "patient011",
  "password": "demo12345",
  "role": "user",
  "login_context": {
    "ip": "202.96.64.68",
    "region": "广东省",
    "city": "广州市",
    "country_name": "China",
    "latitude": 23.1291,
    "longitude": 113.2644
  }
}
```

**成功响应**

返回的是账号摘要，不是简单 `"created": true`。

前端可以直接把返回结果插入列表。

---

### 6.6 批量创建账号

**接口**

`POST /auth/users/batch`

**用途**

- 批量生成演示账号
- 答辩时快速造账号数据

**是否需要鉴权**

- 是，且必须是管理员

**请求体**

```json
{
  "count": 10,
  "username_prefix": "patient",
  "password": "demo12345",
  "role": "user",
  "is_active": true,
  "generate_china_location": true,
  "generate_profile": true,
  "email_domain": "demo.local"
}
```

**说明**

- `count`
  - 1 到 100
- `username_prefix`
  - 例如传 `patient`
  - 后端会生成 `patient001`、`patient002`
- `generate_profile`
  - 自动生成中文姓名
- `generate_china_location`
  - 自动生成中国 IP 和定位

**成功响应**

返回数组，每项结构与 `GET /auth/users` 的单项类似。

---

### 6.7 删除单个账号

**接口**

`DELETE /auth/users/{id}`

**用途**

- 管理员删除指定账号

**是否需要鉴权**

- 是，且必须是管理员

**成功响应**

```json
{
  "deleted": true,
  "username": "patient011"
}
```

**注意**

- 不能删除当前登录管理员自己

---

### 6.8 批量删除账号

**接口**

`POST /auth/users/batch-delete`

**用途**

- 管理员批量删除账号

**是否需要鉴权**

- 是，且必须是管理员

**请求体**

```json
{
  "user_ids": [12, 13, 14]
}
```

**成功响应**

```json
{
  "deleted": true,
  "deleted_count": 3,
  "usernames": ["patient011", "patient012", "patient013"]
}
```

## 7. 设备接口

---

### 7.1 获取设备列表

**接口**

`GET /devices/`

注意这个接口当前路径有结尾斜杠。

**用途**

- 设备列表页
- 设备绑定结果查看

**是否需要鉴权**

- 是

**查询参数**

- `user_id`
  - 管理员可选
  - 指定后只看某个用户的设备

示例：

```text
GET /devices/?user_id=2
```

**成功响应**

```json
[
  {
    "device_id": "ring-001",
    "name": "ring-001",
    "device_type": "smart-ring",
    "source": "wechat-miniapp",
    "last_seen_at": "2026-03-16T02:10:00+08:00",
    "alias": "父亲戒指",
    "owner_user_id": 2,
    "owner_username": "patient001",
    "unread_alerts": 3,
    "latest_measurement_at": "2026-03-16T02:04:39+08:00"
  }
]
```

**字段说明**

- `alias`
  - 用户绑定时给设备起的别名
- `owner_user_id` / `owner_username`
  - 当前激活绑定用户
- `unread_alerts`
  - 该设备未读告警数
- `latest_measurement_at`
  - 最近测量时间

---

### 7.2 绑定设备

**接口**

`POST /devices/bind`

**用途**

- 创建设备
- 或把已有设备绑定到某个用户

**是否需要鉴权**

- 是

**请求体**

```json
{
  "device_id": "ring-002",
  "name": "ring-002",
  "alias": "测试戒指",
  "source": "wechat-miniapp"
}
```

管理员如果要给指定用户绑定，可传：

```json
{
  "device_id": "ring-002",
  "alias": "测试戒指",
  "user_id": 2
}
```

**成功响应**

```json
{
  "id": 5,
  "device_id": "ring-002",
  "device_name": "ring-002",
  "alias": "测试戒指",
  "is_active": true,
  "bound_at": "2026-03-16T02:20:00+08:00"
}
```

**注意**

- 同一个设备只能有一个活跃绑定
- 绑定到新用户时，旧活跃绑定会自动失效

---

### 7.3 获取设备状态

**接口**

`GET /devices/{device_id}/status`

**用途**

- 设备详情页顶部状态卡片
- 首页设备状态概览

**是否需要鉴权**

- 是

**查询参数**

- `user_id`
  - 管理员可选

**成功响应**

```json
{
  "device_id": "ring-001",
  "name": "ring-001",
  "source": "wechat-miniapp",
  "last_seen_at": "2026-03-16T02:10:00+08:00",
  "unread_alerts": 3,
  "latest_measurement": {
    "id": 21,
    "measured_at": "2026-03-16T02:04:39+08:00",
    "packet_kind": "heart_rate",
    "parsed": {
      "heartRate": 121,
      "hrv": 42,
      "stress": 88,
      "temperature": 37.24
    },
    "analysis": {
      "risk_level": "critical",
      "risk_score": 0.99,
      "summary": "实时异常 ..."
    }
  }
}
```

## 8. 原始包上报接口

---

### 8.1 上报原始设备包

**接口**

`POST /packets`

**用途**

- 采集端上传设备原始数据
- 后端解析、分析、告警都从这里触发

**是否需要鉴权**

- 否，但建议有条件时带 Token

**请求体**

```json
{
  "device_id": "ring-001",
  "client_time": "2026-03-15T14:30:00+08:00",
  "source": "wechat-miniapp",
  "session_key": "session-20260316-001",
  "payload": {
    "frame_hex": "00 00 31 00 03 78 28 55 8E 0E",
    "frame_bytes": [0, 0, 49, 0, 3, 120, 40, 85, 142, 14]
  }
}
```

**必填字段**

- `device_id`
- `client_time`
- `payload`

**payload 约束**

至少要有一个：

- `frame_hex`
- `frame_bytes`

**关于 `session_key`**

- 可选
- 如果传，会参与 `UploadSession` 聚合
- 可用于把一次连续采集视为一个上传会话

**用户归属规则**

- 如果请求带了已登录 Token，优先用当前登录用户
- 如果没带 Token，则尝试根据设备当前激活绑定推断用户

**成功响应**

返回的是测量记录对象，不是简单确认。

```json
{
  "id": 21,
  "device_id": "ring-001",
  "user_id": 2,
  "username": "patient001",
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
    "heartRate": 120,
    "hrv": 40,
    "stress": 85,
    "temperature": 37.26
  },
  "analysis": {
    "algorithm_version": "rules-window-baseline-v2",
    "risk_level": "high",
    "risk_score": 0.78,
    "labels": ["较高异常心律风险"],
    "triggers": [
      "realtime_tachycardia",
      "realtime_hrv_instability"
    ],
    "details": {
      "realtime_flags": ["realtime_tachycardia", "realtime_hrv_instability"],
      "window_flags": [],
      "baseline_flags": [],
      "window_stats": {},
      "baselines": {},
      "wearing_effective": true
    },
    "summary": "实时异常 ...",
    "should_alert": true
  },
  "alert_state": {
    "has_alert": true,
    "latest_alert_id": 7,
    "level": "high",
    "status": "unread"
  }
}
```

**前端重点**

- `raw_payload.payload` 保持原样
- `parsed` 直接用于展示
- `analysis` 用于风险 UI
- `alert_state` 用于角标或跳转

## 9. 测量接口

---

### 9.1 获取测量列表

**接口**

`GET /measurements`

**用途**

- 测量列表页
- 历史测量查询

**是否需要鉴权**

- 是

**查询参数**

- `device_id`
  - 可选
- `start`
  - ISO 8601 时间字符串
- `end`
  - ISO 8601 时间字符串
- `user_id`
  - 管理员可选

示例：

```text
GET /measurements?device_id=ring-001&start=2026-03-15T00:00:00+08:00&end=2026-03-16T23:59:59+08:00
```

管理员查看某个用户：

```text
GET /measurements?user_id=2
```

**成功响应**

返回数组，每项结构与 `POST /packets` 的响应基本一致。

**当前字段**

- `id`
- `device_id`
- `user_id`
- `username`
- `measured_at`
- `packet_kind`
- `raw_payload`
- `parsed`
- `analysis`
- `alert_state`

**`parsed` 常见字段**

根据不同包类型，可能出现：

- `batteryLevel`
- `batteryState`
- `heartRate`
- `hrv`
- `stress`
- `oxygen`
- `oxygenHeartRate`
- `temperature`
- `oxygenTemperature`
- `wearStatus`
- `measurementStatus`

前端要做兼容：

- 不同 `packet_kind` 下字段不一定都有
- 不能假设每条记录同时有心率、血氧、温度

---

### 9.2 获取最新测量

**接口**

`GET /measurements/latest`

**用途**

- 仪表盘最新状态
- 设备详情页最新值

**是否需要鉴权**

- 是

**查询参数**

- `device_id`
  - 可选
- `user_id`
  - 管理员可选

**成功响应**

返回单条测量对象，结构与测量列表单项一致。

**没有数据时**

返回：

```json
{
  "detail": "暂无测量数据。"
}
```

HTTP 状态码：

- `404`

---

### 9.3 获取测量趋势

**接口**

`GET /measurements/trends`

**用途**

- 图表页
- Dashboard 趋势图
- 周/月统计组件

**是否需要鉴权**

- 是

**查询参数**

- `user_id`
  - 管理员可选

**成功响应**

```json
{
  "daily": [
    {
      "label": "2026-03-10",
      "measurement_count": 5,
      "high_risk_count": 2,
      "alert_count": 1,
      "avg_heart_rate": 86.4,
      "avg_oxygen": 96.5
    }
  ],
  "weekly": [
    {
      "label": "2026-03-09",
      "measurement_count": 24,
      "high_risk_count": 8,
      "alert_count": 5,
      "avg_heart_rate": 91.2,
      "avg_oxygen": 95.9
    }
  ]
}
```

**字段说明**

- `daily`
  - 最近 7 天
- `weekly`
  - 最近 8 周
- `label`
  - 天或周起始日
- `measurement_count`
  - 测量总数
- `high_risk_count`
  - 风险等级为 `high` 或 `critical` 的测量数
- `alert_count`
  - 告警数
- `avg_heart_rate`
  - 平均心率
- `avg_oxygen`
  - 平均血氧

**前端注意**

- 没有数据的桶也会返回
- 空桶的平均值是 `null`

---

### 9.4 获取单条测量的 AI 解读

**接口**

`POST /measurements/{measurement_id}/llm-insight`

**用途**

- 对某条测量生成 AI 中文解释
- 用于患者说明页、详情抽屉、AI 助手面板

**是否需要鉴权**

- 是

**请求体**

空对象即可：

```json
{}
```

**成功响应**

```json
{
  "available": true,
  "mode": "template",
  "provider": "template",
  "model": "gpt-4o-mini",
  "prompt": "你是房颤监测系统的健康分析助手...",
  "context": {
    "measurement_id": 21,
    "device_id": "ring-001",
    "username": "patient001",
    "measured_at": "2026-03-16T02:04:39+08:00",
    "packet_kind": "heart_rate",
    "parsed": {},
    "analysis": {}
  },
  "content": "1. 结果解读\n风险等级：high ...",
  "template_content": "1. 结果解读\n风险等级：high ...",
  "source": "template"
}
```

**字段说明**

- `available`
  - 当前是否启用 AI
- `source`
  - `template`
  - `llm`
  - `template_fallback`
- `content`
  - 最终建议前端显示的内容
- `prompt`
  - 调试时可看，生产 UI 一般不直接展示
- `context`
  - AI 看到的结构化上下文

**前端建议**

- 页面展示时优先用 `content`
- 不要直接把 `prompt` 给终端用户看

## 10. 告警接口

---

### 10.1 获取告警列表

**接口**

`GET /alerts`

**用途**

- 告警中心
- 设备详情页告警记录

**是否需要鉴权**

- 是

**查询参数**

- `device_id`
  - 可选
- `user_id`
  - 管理员可选

**成功响应**

```json
[
  {
    "id": 7,
    "device_id": "ring-001",
    "user_id": 2,
    "username": "patient001",
    "measurement_id": 21,
    "level": "critical",
    "title": "高危房颤风险预警",
    "message": "实时异常 ...",
    "trigger_codes": [
      "realtime_tachycardia",
      "window_repeated_tachycardia_30m"
    ],
    "status": "unread",
    "is_read": false,
    "read_at": null,
    "created_at": "2026-03-16T02:04:39+08:00"
  }
]
```

**字段说明**

- `level`
  - `low | moderate | high | critical`
- `trigger_codes`
  - 规则命中列表
- `status`
  - `unread | read`
- `is_read`
  - 布尔值，前端可直接用

---

### 10.2 标记告警已读

**接口**

`POST /alerts/{alert_id}/read`

**用途**

- 告警详情页“标记已读”
- 告警列表的快速处理

**是否需要鉴权**

- 是

**请求体**

空对象即可：

```json
{}
```

**成功响应**

返回更新后的告警对象。

关键变化：

- `status = "read"`
- `is_read = true`
- `read_at` 有时间

## 11. Dashboard 与 AI 设置接口

---

### 11.1 获取 Dashboard 总览

**接口**

`GET /dashboard/overview`

**用途**

- 控制台总览页

**是否需要鉴权**

- 是

**查询参数**

- `user_id`
  - 管理员可选

**成功响应**

```json
{
  "counts": {
    "devices": 12,
    "measurements": 248,
    "alerts": 31,
    "unread_alerts": 9
  },
  "user_summaries": [
    {
      "id": 2,
      "username": "patient001",
      "role": "user",
      "last_login_ip": "39.224.1.135",
      "last_login_location": {
        "country": "China",
        "region": "北京市",
        "city": "北京市",
        "latitude": 39.9042,
        "longitude": 116.4074
      },
      "device_count": 1,
      "measurement_count": 18,
      "unread_alert_count": 3
    }
  ],
  "risk_distribution": [
    {
      "risk_level": "critical",
      "total": 5
    }
  ],
  "latest_measurements": [
    {
      "id": 21,
      "device_id": "ring-001",
      "user_id": 2,
      "username": "patient001",
      "measured_at": "2026-03-16T02:04:39+08:00",
      "packet_kind": "heart_rate",
      "parsed": {},
      "risk_level": "critical"
    }
  ],
  "latest_alerts": [
    {
      "id": 7,
      "device_id": "ring-001",
      "user_id": 2,
      "username": "patient001",
      "level": "critical",
      "title": "高危房颤风险预警",
      "status": "unread",
      "created_at": "2026-03-16T02:04:39+08:00"
    }
  ]
}
```

**说明**

- 管理员全局查看时，`user_summaries` 是普通用户列表，不包含管理员
- `latest_measurements` 和 `latest_alerts` 也是面向普通用户监测数据

---

### 11.2 获取 AI 设置

**接口**

`GET /ai/settings`

**用途**

- 管理员打开 AI 设置页时读取当前配置

**是否需要鉴权**

- 是，且必须是管理员

**成功响应**

```json
{
  "enabled": true,
  "mode": "template",
  "api_base_url": "",
  "api_key_masked": "",
  "has_api_key": false,
  "model": "gpt-4o-mini",
  "temperature": "0.20",
  "system_prompt": "你是一名经验丰富、严谨负责的心血管内科医生...",
  "updated_at": "2026-03-16T02:00:00+08:00"
}
```

**注意**

- `api_key` 不会明文返回
- 只会返回 `has_api_key` 和 `api_key_masked`

---

### 11.3 更新 AI 设置

**接口**

`PUT /ai/settings`

**用途**

- 保存 AI 接入方式

**是否需要鉴权**

- 是，且必须是管理员

**请求体**

```json
{
  "enabled": true,
  "mode": "openai_compatible",
  "api_base_url": "https://your-llm-provider.example/v1",
  "api_key": "sk-xxxx",
  "model": "gpt-4o-mini",
  "temperature": 0.2,
  "system_prompt": "你是一名经验丰富、严谨负责的心血管内科医生..."
}
```

**`mode` 可选值**

- `disabled`
- `template`
- `openai_compatible`

**说明**

- `template`
  - 不调用外部模型
  - 直接返回模板化中文解读
- `openai_compatible`
  - 调兼容 OpenAI Chat Completions 的模型接口

---

### 11.4 测试 AI 配置

**接口**

`POST /ai/settings/test`

**用途**

- 在 AI 设置页里点击“测试可用性”

**是否需要鉴权**

- 是，且必须是管理员

**请求体**

可以直接传当前表单内容：

```json
{
  "enabled": true,
  "mode": "template",
  "model": "gpt-4o-mini",
  "temperature": 0.2,
  "system_prompt": "你是一名经验丰富、严谨负责的心血管内科医生..."
}
```

**成功响应**

```json
{
  "available": true,
  "mode": "template",
  "provider": "template",
  "model": "gpt-4o-mini",
  "content": "1. 结果解读\n...",
  "template_content": "1. 结果解读\n...",
  "source": "template",
  "ok": true
}
```

**字段说明**

- `ok`
  - 当前这次测试是否可用
- `source`
  - 最终是模板结果还是真实 LLM
- `error`
  - 外部模型失败时会有

## 12. 前端对接建议

### 12.1 登录建议

- 控制台用 `/auth/console-login`
- 普通用户端用 `/auth/login`
- Web 登录时建议先调用 `https://ipapi.co/json/`
- 把返回的 `ip / city / region / latitude / longitude` 放进 `login_context`

### 12.2 列表页建议

- 测量页使用 `GET /measurements`
- 告警页使用 `GET /alerts`
- 设备页使用 `GET /devices/`

管理员点击某个用户后，统一追加：

- `?user_id=<id>`

### 12.3 详情页建议

- 设备详情顶部状态：`GET /devices/{device_id}/status`
- 最新测量卡片：`GET /measurements/latest?device_id=...`
- 告警记录：`GET /alerts?device_id=...`

### 12.4 图表建议

- 趋势图：`GET /measurements/trends`
- 风险分布：`GET /dashboard/overview`

### 12.5 AI 建议

- 优先显示 `content`
- 如果 `source = template_fallback`，说明外部模型失败，仍可正常展示回退内容

## 13. 典型错误码

### 400

参数错误。

常见情况：

- 缺少必填字段
- 密码太短
- `payload` 没有 `frame_hex/frame_bytes`
- 批量删除传空数组

### 401

未登录或 Token 无效。

### 403

权限不足。

常见情况：

- 普通用户访问管理员接口
- 非管理员调用 `/auth/console-login`

### 404

资源不存在。

常见情况：

- `measurement_id` 不存在
- `alert_id` 不存在
- 当前作用域下没有最新测量

## 14. 本轮核对与测试结果

本手册整理时已核对以下内容：

- 路由文件
- 视图权限
- 序列化字段
- 管理员 `user_id` 作用域逻辑
- AI 设置与 AI 测试逻辑

建议前端联调时优先验证这条最短链路：

1. `/auth/console-login`
2. `/auth/users`
3. `/measurements`
4. `/alerts`
5. `/measurements/trends`
6. `/ai/settings`

如果需要快速造联调数据，优先使用：

- `python manage.py generate_mock_monitoring_data`

对应说明见：

- `document/mock-data-testing.md`
