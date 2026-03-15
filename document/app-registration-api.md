# App 注册接口说明

## 目标

当前系统除了管理员在控制台手工创建账号之外，已经新增面向 App 的公共注册接口：

- `POST /api/v1/auth/register`

这个接口的定位是：

- 给普通用户自助注册
- 自动创建 `user` 角色账号
- 可选记录注册时 IP 和地理位置
- 可选创建基础患者资料
- 注册成功后直接返回 Token，便于 App 立即进入登录态

## 为什么需要单独注册接口

当前已有两类账号创建方式：

- 管理员控制台：
  - `POST /api/v1/auth/users`
  - 只允许管理员调用
- 普通用户 App：
  - `POST /api/v1/auth/register`
  - 允许匿名访问

这两种接口不应混用。

原因是：

- App 注册必须限制为普通用户
- 不能让公开接口带有管理员角色创建能力
- App 注册成功后通常要立即返回 Token
- 控制台建号更偏后台管理，不适合直接给用户端使用

## 接口说明

### 请求地址

```text
POST /api/v1/auth/register
```

### 认证要求

- 不需要登录

### 请求体示例

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

## 字段说明

### 基础账号字段

- `username`
  - 必填
  - 唯一
- `password`
  - 必填
  - 最少 8 位
- `email`
  - 可选
- `first_name`
  - 可选
- `last_name`
  - 可选

### `login_context`

可选字段，用于记录用户注册/首次登录时的来源位置。

支持：

- `ip`
- `city`
- `region`
- `country_name`
- `latitude`
- `longitude`

推荐 App 端在注册前自行获取并上传。

## `profile`

可选字段，用于初始化患者资料表 `PatientProfile`。

当前支持：

- `full_name`
- `phone`
- `age`
- `sex`
- `notes`

如果不传 `full_name`，后端会自动用：

- `last_name + first_name`

作为默认姓名。

## 成功响应

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

## 行为约束

这个接口有以下固定行为：

- 注册出来的账号永远是 `role = user`
- `is_staff = false`
- `is_superuser = false`
- 自动创建 `PatientProfile`
- 自动返回 Token

也就是说：

- App 注册成功后，可以直接进入已登录状态
- 不需要再额外发一次 `/auth/login`

## 前端使用建议

### 推荐注册流程

1. App 采集用户名、密码、邮箱、姓名、手机号等信息
2. 如果前端能拿到公网 IP 与地理信息，构造 `login_context`
3. 调用 `POST /auth/register`
4. 将响应里的 `token` 存入本地
5. 后续请求统一带：

```http
Authorization: Token <token>
```

## 安全建议

当前是毕设一期实现，已经满足基本功能，但后续正式上线建议继续补：

- 图形验证码或短信验证码
- 用户名/邮箱/手机号重复校验提示优化
- 注册频率限制
- 更完善的密码强度策略

## 当前实现状态

当前接口已经落地到：

- `backend/accounts/views.py`
- `backend/accounts/serializers.py`
- `backend/accounts/urls.py`

并已纳入自动化测试。
