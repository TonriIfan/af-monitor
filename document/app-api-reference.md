# HeartGuard App API 对接文档

## 1. 适用范围

这份文档专门面向 App 前端。

它覆盖三期接口：

- 第一期：App 最低可用闭环
- 第二期：体验增强与分析增强
- 第三期：答辩加分功能

当前生产环境建议基地址：

```text
https://api.heartguard.cn/api/v1
```

本地开发：

```text
http://127.0.0.1:8000/api/v1
```

## 2. 鉴权

除注册和登录外，其余接口都需要：

```http
Authorization: Token <token>
```

注册成功和登录成功都会直接返回 `token`。

---

## 3. 第一期接口

### 3.1 注册

`POST /auth/register`

用途：

- 普通用户注册
- 自动创建患者资料
- 直接返回登录态

请求体示例：

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

成功响应：

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

### 3.2 登录

`POST /auth/login`

用途：

- 普通用户登录

请求体：

```json
{
  "username": "patient-mobile-001",
  "password": "demo12345",
  "login_context": {
    "ip": "202.96.64.68",
    "city": "广州市",
    "region": "广东省",
    "country_name": "China",
    "latitude": 23.1291,
    "longitude": 113.2644
  }
}
```

响应结构和注册成功一致。

### 3.3 获取当前用户

`GET /auth/me`

用途：

- App 启动后刷新当前登录用户信息
- 不依赖本地缓存的旧资料

响应示例：

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

### 3.4 退出登录

`POST /auth/logout`

用途：

- 让当前 Token 失效

请求体：

```json
{}
```

响应：

```json
{
  "logged_out": true
}
```

### 3.5 获取患者资料

`GET /profile`

响应：

```json
{
  "full_name": "陈芳婷",
  "phone": "13800138000",
  "age": 61,
  "sex": "female",
  "notes": "有心悸史"
}
```

### 3.6 更新患者资料

`PUT /profile`

请求体：

```json
{
  "full_name": "陈芳婷",
  "phone": "13800138000",
  "age": 61,
  "sex": "female",
  "notes": "近两周偶有心悸"
}
```

响应：

返回更新后的资料对象。

### 3.7 首页摘要

`GET /home/summary`

用途：

- App 首页聚合数据

响应示例：

```json
{
  "user": {
    "id": 2,
    "username": "patient001",
    "role": "user"
  },
  "counts": {
    "devices": 1,
    "measurements": 18,
    "alerts": 13,
    "unread_alerts": 3
  },
  "current_device": {
    "device_id": "ring-001",
    "name": "ring-001",
    "source": "wechat-miniapp",
    "last_seen_at": "2026-03-16T02:04:39+08:00",
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
  },
  "latest_measurement": {
    "id": 21,
    "device_id": "ring-001",
    "measured_at": "2026-03-16T02:04:39+08:00",
    "packet_kind": "heart_rate",
    "parsed": {},
    "analysis": {
      "risk_level": "critical",
      "risk_score": 0.99,
      "summary": "实时异常 ...",
      "triggers": [
        "realtime_tachycardia"
      ]
    }
  },
  "latest_alert": {
    "id": 7,
    "level": "critical",
    "title": "高危房颤风险预警",
    "message": "实时异常 ...",
    "created_at": "2026-03-16T02:04:39+08:00"
  },
  "trend_preview": [
    {
      "label": "2026-03-16",
      "measurement_count": 4,
      "high_risk_count": 2,
      "alert_count": 1,
      "avg_heart_rate": 95.5,
      "avg_oxygen": 96.0
    }
  ]
}
```

### 3.8 获取当前绑定设备

`GET /devices/current`

用途：

- App 快速拿当前设备

响应示例：

```json
{
  "device_id": "ring-001",
  "name": "ring-001",
  "device_type": "smart-ring",
  "source": "wechat-miniapp",
  "last_seen_at": "2026-03-16T02:04:39+08:00",
  "alias": "我的戒指",
  "owner_user_id": 2,
  "owner_username": "patient001",
  "unread_alerts": 3,
  "latest_measurement_at": "2026-03-16T02:04:39+08:00"
}
```

### 3.9 用户主动解绑设备

`POST /devices/unbind`

请求体：

```json
{
  "device_id": "ring-001"
}
```

`device_id` 可选。

如果不传，后端会默认解绑当前用户最近一个活跃绑定设备。

响应：

```json
{
  "unbound": true,
  "device_id": "ring-001",
  "user_id": 2,
  "unbound_at": "2026-03-16T03:10:00+08:00"
}
```

### 3.10 测量列表

`GET /measurements`

支持查询参数：

- `device_id`
- `start`
- `end`

返回每条测量的：

- `raw_payload`
- `parsed`
- `analysis`
- `alert_state`

### 3.11 测量详情

`GET /measurements/{measurement_id}`

返回单条测量完整信息，结构与测量列表单项一致。

### 3.12 最新测量

`GET /measurements/latest`

支持参数：

- `device_id`

### 3.13 告警列表

`GET /alerts`

支持参数：

- `device_id`

### 3.14 告警详情

`GET /alerts/{alert_id}`

### 3.15 告警未读数

`GET /alerts/unread-count`

响应：

```json
{
  "unread_count": 3
}
```

### 3.16 单条告警已读

`POST /alerts/{alert_id}/read`

请求体：

```json
{}
```

### 3.17 全部告警已读

`POST /alerts/read-all`

请求体：

```json
{}
```

响应：

```json
{
  "updated_count": 3
}
```

---

## 4. 第二期接口

### 4.1 趋势统计

`GET /measurements/trends`

返回：

- `daily`
- `weekly`

每项包含：

- `label`
- `measurement_count`
- `high_risk_count`
- `alert_count`
- `avg_heart_rate`
- `avg_oxygen`

### 4.2 图表数据

`GET /measurements/chart`

查询参数：

- `metric=heart_rate|oxygen|temperature`
- `range=7d|30d`

示例：

```text
GET /measurements/chart?metric=heart_rate&range=7d
```

响应：

```json
{
  "metric": "heart_rate",
  "range": "7d",
  "points": [
    {
      "measurement_id": 21,
      "measured_at": "2026-03-16T02:04:39+08:00",
      "value": 121.0,
      "device_id": "ring-001"
    }
  ],
  "summary": {
    "count": 7,
    "avg": 89.7,
    "min": 72.0,
    "max": 121.0
  }
}
```

### 4.3 最新分析结果

`GET /analysis/latest`

响应：

```json
{
  "measurement_id": 21,
  "device_id": "ring-001",
  "measured_at": "2026-03-16T02:04:39+08:00",
  "username": "patient001",
  "parsed": {},
  "analysis": {
    "algorithm_version": "rules-window-baseline-v2",
    "risk_level": "critical",
    "risk_score": 0.99,
    "labels": [],
    "triggers": [
      "realtime_tachycardia",
      "window_repeated_tachycardia_30m"
    ],
    "details": {},
    "summary": "实时异常 ...",
    "should_alert": true
  }
}
```

### 4.4 分析历史

`GET /analysis/history`

查询参数：

- `limit`

示例：

```text
GET /analysis/history?limit=20
```

响应：

```json
{
  "items": [
    {
      "measurement_id": 21,
      "device_id": "ring-001",
      "measured_at": "2026-03-16T02:04:39+08:00",
      "packet_kind": "heart_rate",
      "risk_level": "critical",
      "risk_score": 0.99,
      "summary": "实时异常 ...",
      "triggers": [
        "realtime_tachycardia"
      ]
    }
  ]
}
```

### 4.5 症状反馈

`POST /feedback/symptoms`

用途：

- 用户主动记录症状

请求体：

```json
{
  "symptoms": ["palpitation", "dizziness"],
  "severity": 4,
  "duration_minutes": 15,
  "notes": "晚间发作",
  "occurred_at": "2026-03-15T17:30:00+08:00"
}
```

响应：

```json
{
  "id": 1,
  "symptoms": ["palpitation", "dizziness"],
  "severity": 4,
  "duration_minutes": 15,
  "notes": "晚间发作",
  "occurred_at": "2026-03-15T17:30:00+08:00",
  "created_at": "2026-03-16T03:00:00+08:00"
}
```

### 4.6 推送设备登记

`POST /push/register-device`

用途：

- 保存 App 推送 token

请求体：

```json
{
  "device_token": "push-token-001",
  "platform": "android",
  "app_version": "1.0.0",
  "device_name": "Pixel 8",
  "is_active": true
}
```

响应：

```json
{
  "id": 1,
  "device_token": "push-token-001",
  "platform": "android",
  "app_version": "1.0.0",
  "device_name": "Pixel 8",
  "is_active": true,
  "last_seen_at": "2026-03-16T03:05:00+08:00",
  "created_at": "2026-03-16T03:05:00+08:00"
}
```

---

## 5. 第三期接口

### 5.1 批量上报测量

`POST /measurements/batch`

用途：

- App 离线缓存后批量补传

请求体：

```json
{
  "items": [
    {
      "device_id": "ring-001",
      "client_time": "2026-03-15T17:00:00+08:00",
      "source": "app-batch",
      "payload": {
        "frame_hex": "00 00 31 00 03 78 28 55 8E 0E"
      }
    },
    {
      "device_id": "ring-001",
      "client_time": "2026-03-15T17:10:00+08:00",
      "source": "app-batch",
      "payload": {
        "frame_hex": "00 00 32 00 03 78 5D 6E 0E"
      }
    }
  ]
}
```

响应：

```json
{
  "created_count": 2,
  "items": [
    {
      "id": 31,
      "device_id": "ring-001"
    }
  ]
}
```

### 5.2 周报

`GET /reports/weekly`

响应：

```json
{
  "period_days": 7,
  "start_at": "2026-03-09T03:00:00+08:00",
  "end_at": "2026-03-16T03:00:00+08:00",
  "measurement_count": 18,
  "alert_count": 13,
  "peak_risk_level": "critical",
  "avg_heart_rate": 92.4,
  "avg_oxygen": 95.6,
  "top_triggers": [
    {
      "code": "realtime_tachycardia",
      "count": 7
    }
  ],
  "summary": "最近 7 天共记录 18 条测量，产生 13 条告警，最高风险等级为 critical。"
}
```

### 5.3 月报

`GET /reports/monthly`

返回结构与周报一致，`period_days = 30`。

### 5.4 单条测量 AI 解读

`POST /measurements/{measurement_id}/llm-insight`

用途：

- 对单次测量做患者可读解释

### 5.5 AI 健康问答

`POST /ai/chat`

用途：

- 面向患者的 AI 问答
- 会结合最近分析结果、趋势摘要和未读告警数量

请求体：

```json
{
  "message": "我现在需要马上去医院吗？"
}
```

响应：

```json
{
  "available": true,
  "mode": "template",
  "provider": "template",
  "model": "gpt-4o-mini",
  "prompt": "你是房颤监测系统中的健康解读助手...",
  "context": {
    "user_id": 2,
    "username": "patient001",
    "latest_analysis": {},
    "trend_preview": [],
    "unread_alert_count": 3
  },
  "content": "针对你的问题“我现在需要马上去医院吗？”，系统先给出辅助说明：...",
  "source": "template"
}
```

## 6. 当前建议的 App 联调顺序

最推荐按下面顺序接：

1. `/auth/register`
2. `/auth/login`
3. `/auth/me`
4. `/profile`
5. `/home/summary`
6. `/devices/current`
7. `/measurements`
8. `/measurements/{id}`
9. `/alerts`
10. `/alerts/unread-count`
11. `/measurements/trends`
12. `/analysis/latest`
13. `/ai/chat`

## 7. 本轮实现状态

本轮已经补齐：

- 注册、当前用户、退出登录
- 患者资料读写
- 首页摘要
- 当前设备、解绑设备
- 测量详情、告警详情、全部已读、未读计数
- 图表、分析最新值、分析历史
- 症状反馈、推送登记
- 批量上报、周报、月报
- AI 问答

如果后续 App 需要：

- 验证码注册
- 密码找回
- 推送下发
- 周报月报 PDF 化

可以在这一套接口基础上继续往上加。
