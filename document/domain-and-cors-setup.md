# 域名与跨域配置说明

## 目标域名规划

当前项目建议按下面的方式拆分域名：

- `heartguard.cn`
  - 用作官网展示页、项目介绍页、下载入口
- `console.heartguard.cn`
  - 用作后台管理控制台
- `api.heartguard.cn`
  - 用作 Django REST API

这种拆分有几个直接好处：

- 前后端职责清晰
- 后续官网、管理台、App、小程序可以共存
- 部署和反向代理更容易维护
- 权限和安全边界更清楚

## 已配置的后端设置

后端配置文件：

- `backend/config/settings.py`

已默认加入以下域名：

### ALLOWED_HOSTS

默认包含：

- `127.0.0.1`
- `localhost`
- `heartguard.cn`
- `console.heartguard.cn`
- `api.heartguard.cn`

### CORS_ALLOWED_ORIGINS

默认包含：

- `http://localhost:5173`
- `http://127.0.0.1:5173`
- `https://heartguard.cn`
- `https://console.heartguard.cn`

说明：

- 控制台部署到 `console.heartguard.cn` 后，可以直接跨域访问 `api.heartguard.cn`
- 官网如果未来要展示公开数据或做演示，也保留了 `heartguard.cn` 的跨域入口

### CSRF_TRUSTED_ORIGINS

默认包含：

- `http://localhost:5173`
- `http://127.0.0.1:5173`
- `https://heartguard.cn`
- `https://console.heartguard.cn`
- `https://api.heartguard.cn`

说明：

- 即使当前控制台主要走 Token 鉴权，这个配置仍然建议保留
- 后续如果接入 Django Session、后台表单或其他管理接口，会更稳

### CORS_ALLOW_CREDENTIALS

默认开启：

- `true`

### SECURE_PROXY_SSL_HEADER

已设置：

- `('HTTP_X_FORWARDED_PROTO', 'https')`

作用：

- 当你通过 Nginx 或云服务器反向代理接入 HTTPS 时，Django 可以正确识别外层协议

## 环境变量文件

### 后端

示例文件：

- `backend/.env.example`

你部署时建议复制为：

- `backend/.env`

### 前端控制台

开发环境示例：

- `console/.env.example`

生产环境示例：

- `console/.env.production.example`

其中生产环境 API 地址建议为：

```env
VITE_API_BASE_URL=https://api.heartguard.cn/api/v1
```

## 推荐部署关系

### 官网

- 域名：`heartguard.cn`
- 可以后续单独做 Vue 静态站、营销页、项目展示页

### 控制台

- 域名：`console.heartguard.cn`
- 运行当前 `console` 前端产物

### API

- 域名：`api.heartguard.cn`
- 反向代理到 Django `gunicorn / uvicorn / runserver` 所在端口

## 典型反向代理思路

### 控制台域名

- `console.heartguard.cn` 指向前端打包后的静态文件目录

### API 域名

- `api.heartguard.cn` 指向 Django 服务

例如：

- `https://console.heartguard.cn` -> Vue 构建产物
- `https://api.heartguard.cn/api/v1/...` -> Django

## 开发与生产的区别

### 开发环境

- 控制台：`http://localhost:5173`
- API：`http://127.0.0.1:8000`

### 生产环境

- 控制台：`https://console.heartguard.cn`
- API：`https://api.heartguard.cn`
- 官网：`https://heartguard.cn`

## 当前建议

现阶段你可以先：

1. 保留 `heartguard.cn` 作为官网展示位
2. 把控制台规划为 `console.heartguard.cn`
3. 把后端 API 规划为 `api.heartguard.cn`
4. 前端生产环境统一指向 `https://api.heartguard.cn/api/v1`

这样后续做官网时，不需要再重构当前控制台和后端的部署边界。
