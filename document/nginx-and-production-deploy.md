# HeartGuard 生产部署说明

## 目标

本说明用于将当前系统按以下域名部署到线上：

- `heartguard.cn`
  - 官网展示站
- `console.heartguard.cn`
  - Vue 管理控制台
- `api.heartguard.cn`
  - Django REST API

## 推荐部署结构

推荐使用一台 Linux 云服务器，基础结构如下：

- `Nginx`
  - 对外提供 HTTPS
  - 托管官网和控制台静态文件
  - 反向代理 Django API
- `Django`
  - 运行在本机内网端口，例如 `127.0.0.1:8000`
- `MySQL`
  - 生产数据库

如果你暂时不部署官网，也可以先只部署：

- `console.heartguard.cn`
- `api.heartguard.cn`

## DNS 配置建议

在域名服务商控制台中添加以下记录：

| 主机记录 | 记录类型 | 值 |
| --- | --- | --- |
| `@` | `A` | 你的服务器公网 IP |
| `console` | `A` | 你的服务器公网 IP |
| `api` | `A` | 你的服务器公网 IP |

如果你后面接 CDN，可以把官网和控制台接 CDN，API 仍建议直接回源或使用单独安全策略。

## 目录建议

服务器上建议使用如下目录结构：

```text
/srv/heartguard/
  backend/
  console-dist/
  website-dist/
  venv/
  logs/
```

例如：

- `/srv/heartguard/backend`
  - Django 项目代码
- `/srv/heartguard/console-dist`
  - `console` 执行 `npm run build` 之后的产物
- `/srv/heartguard/website-dist`
  - 官网静态站产物
- `/srv/heartguard/venv`
  - Python 虚拟环境

## Django 生产环境配置

### 1. 环境变量

建议在服务器的 `backend/.env` 中至少配置：

```dotenv
SECRET_KEY=请替换成强随机字符串
DEBUG=false
ALLOWED_HOSTS=127.0.0.1,localhost,heartguard.cn,console.heartguard.cn,api.heartguard.cn
CORS_ALLOWED_ORIGINS=https://heartguard.cn,https://console.heartguard.cn
CORS_ALLOW_ALL_ORIGINS=false
CORS_ALLOW_CREDENTIALS=true
CSRF_TRUSTED_ORIGINS=https://heartguard.cn,https://console.heartguard.cn,https://api.heartguard.cn

DB_ENGINE=mysql
DB_NAME=yf_monitor
DB_USER=你的数据库用户
DB_PASSWORD=你的数据库密码
DB_HOST=127.0.0.1
DB_PORT=3306
```

### 2. 初始化命令

```bash
cd /srv/heartguard/backend
/srv/heartguard/venv/bin/python manage.py migrate
/srv/heartguard/venv/bin/python manage.py collectstatic --noinput
/srv/heartguard/venv/bin/python manage.py seed_demo_admin
```

说明：

- `seed_demo_admin` 只适合初始化演示环境
- 正式环境建议改成你自己的管理员账号

### 3. Django 进程建议

生产环境不要继续用 `runserver`。

更稳的方式是：

- `gunicorn`
- 或 `uvicorn + ASGI`

例如使用 `gunicorn`：

```bash
/srv/heartguard/venv/bin/pip install gunicorn
cd /srv/heartguard/backend
/srv/heartguard/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3
```

如果后面你要长期运行，建议再配 `systemd` 守护。

## Vue 控制台生产配置

### 1. 环境变量

在 `console` 目录中创建生产环境变量：

```dotenv
VITE_API_BASE_URL=https://api.heartguard.cn/api/v1
```

项目里已有示例文件：

- `console/.env.production.example`

### 2. 构建

```bash
cd /srv/heartguard/console-source
npm install
npm run build
```

然后把构建产物部署到：

- `/srv/heartguard/console-dist`

## Nginx 配置示例

下面给出一个可直接改路径后使用的示例。

### 1. 官网 `heartguard.cn`

```nginx
server {
    listen 80;
    server_name heartguard.cn www.heartguard.cn;
    return 301 https://heartguard.cn$request_uri;
}

server {
    listen 443 ssl http2;
    server_name heartguard.cn;

    ssl_certificate /etc/letsencrypt/live/heartguard.cn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/heartguard.cn/privkey.pem;

    root /srv/heartguard/website-dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### 2. 控制台 `console.heartguard.cn`

```nginx
server {
    listen 80;
    server_name console.heartguard.cn;
    return 301 https://console.heartguard.cn$request_uri;
}

server {
    listen 443 ssl http2;
    server_name console.heartguard.cn;

    ssl_certificate /etc/letsencrypt/live/console.heartguard.cn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/console.heartguard.cn/privkey.pem;

    root /srv/heartguard/console-dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### 3. API `api.heartguard.cn`

```nginx
server {
    listen 80;
    server_name api.heartguard.cn;
    return 301 https://api.heartguard.cn$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.heartguard.cn;

    ssl_certificate /etc/letsencrypt/live/api.heartguard.cn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.heartguard.cn/privkey.pem;

    client_max_body_size 20m;

    location /docs/ {
        alias /srv/heartguard/document-dist/;
        index index.html;
        try_files $uri $uri/ /docs/index.html;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 120s;
    }
}
```

说明：

- `/docs/` 用来挂 VitePress 静态文档站
- `/` 继续反向代理 Django API
- 当前文档站已按 `/docs/` 作为基础路径构建

## HTTPS 证书建议

如果你使用 Linux + Nginx，最常见的方案是：

- `Let's Encrypt`
- `certbot`

例如：

```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx
sudo certbot --nginx -d heartguard.cn -d www.heartguard.cn
sudo certbot --nginx -d console.heartguard.cn
sudo certbot --nginx -d api.heartguard.cn
```

完成后可以检查自动续期：

```bash
sudo certbot renew --dry-run
```

## 上线检查清单

### 后端

- `DEBUG=false`
- `SECRET_KEY` 已替换
- 已切到 MySQL
- `migrate` 已执行
- 管理员账号已创建
- `api.heartguard.cn/api/v1/...` 可正常访问

### 控制台

- `VITE_API_BASE_URL` 已改为 `https://api.heartguard.cn/api/v1`
- `npm run build` 已通过
- `console.heartguard.cn` 打开后能正常登录
- 登录后请求不再报跨域错误

### 官网

- `heartguard.cn` 能打开首页
- 若使用前端路由，已配置 `try_files ... /index.html`

### HTTPS

- 三个域名都已启用 HTTPS
- 浏览器无证书警告
- API 请求为 `https`

## 当前最推荐的上线顺序

建议按下面顺序推进：

1. 先把 `api.heartguard.cn` 跑起来
2. 再把 `console.heartguard.cn` 接上
3. 最后再做 `heartguard.cn` 官网展示

这样可以先把后端和控制台稳定下来，不会被官网开发打断主线。

## 说明

这份文档给的是通用 Linux + Nginx 方案。

如果你后面使用的是：

- 宝塔
- Docker
- 宝塔 + Docker
- 云厂商负载均衡

实现方式会不同，但域名规划和跨域原则不变。
