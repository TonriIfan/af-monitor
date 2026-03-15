# yf-monitor backend

一期后端基于 Django + DRF，负责智能戒指数据接收、协议解析、规则分析、历史查询和告警管理。

## 本地运行

```powershell
python3 -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
cd backend
..\.venv\Scripts\python manage.py migrate
..\.venv\Scripts\python manage.py seed_demo_admin
..\.venv\Scripts\python manage.py createsuperuser
..\.venv\Scripts\python manage.py runserver
```

注意：
- 默认使用 SQLite 便于本地启动。
- 生产或论文演示环境可通过环境变量切换到 MySQL。
- 已允许 `http://localhost:5173` 和 `http://127.0.0.1:5173` 的控制台跨域访问。
- `POST /api/v1/packets` 会保留原始 `payload`，同时返回 `parsed`、`analysis`、`alert_state`。

## 已实现接口

- `POST /api/v1/auth/login`
- `POST /api/v1/devices/bind`
- `POST /api/v1/packets`
- `GET /api/v1/measurements`
- `GET /api/v1/measurements/latest`
- `GET /api/v1/alerts`
- `POST /api/v1/alerts/{id}/read`
- `GET /api/v1/devices/{device_id}/status`
