# 后端分析系统虚拟数据测试说明

## 目标

为了在没有真实智能戒指持续上报数据的情况下测试后端分析能力，系统新增了一个管理命令：

- `generate_mock_monitoring_data`

该命令会直接走现有监测链路：

1. 构造模拟设备数据帧
2. 调用现有 `ingest_packet`
3. 自动触发：
   - 协议解析
   - 风险分析
   - 趋势统计数据累计
   - 告警生成
   - LLM 解读上下文生成

也就是说，这不是“假写数据库”，而是完整模拟真实分析流程。

## 命令位置

- `backend/monitoring/management/commands/generate_mock_monitoring_data.py`

## 基本用法

在项目根目录下执行：

```powershell
cd yf-monitor\backend
..\.venv\Scripts\python manage.py generate_mock_monitoring_data
```

默认会生成：

- 用户：`mock-user`
- 设备：`mock-ring-001`
- 场景：`baseline_spike`
- 包数量：`24`

## 可选参数

### 1. 指定用户和设备

```powershell
..\.venv\Scripts\python manage.py generate_mock_monitoring_data --username patient-demo --device-id ring-demo-001
```

### 2. 指定场景

```powershell
..\.venv\Scripts\python manage.py generate_mock_monitoring_data --scenario normal
```

支持的场景：

- `normal`
  主要生成正常波动数据，适合测试低风险情况

- `high_risk`
  主要生成持续高心率、高 HRV、低血氧等异常数据，适合测试高风险和告警

- `baseline_spike`
  前半段生成较稳定基线，后半段生成明显偏离基线的数据，适合测试“个人基线偏移”

- `trend`
  生成混合正常/异常数据，适合测试日/周趋势统计

### 3. 指定数量和间隔

```powershell
..\.venv\Scripts\python manage.py generate_mock_monitoring_data --scenario trend --count 48 --interval-minutes 60
```

### 4. 指定开始时间

```powershell
..\.venv\Scripts\python manage.py generate_mock_monitoring_data --start-at 2026-03-10T08:00:00+08:00
```

## 推荐测试流程

### 测试 1：单次分析与告警

```powershell
..\.venv\Scripts\python manage.py generate_mock_monitoring_data --scenario high_risk --count 12 --interval-minutes 10 --username risk-user --device-id risk-ring-001
```

然后测试：

- `GET /api/v1/measurements`
- `GET /api/v1/alerts`

观察点：

- 是否出现 `high` 或 `critical`
- 是否生成告警
- `analysis.details` 中是否有 `realtime_flags`、`window_flags`

### 测试 2：个人基线偏移

```powershell
..\.venv\Scripts\python manage.py generate_mock_monitoring_data --scenario baseline_spike --count 30 --interval-minutes 20 --username baseline-user --device-id baseline-ring-001
```

观察点：

- 后期数据是否出现 `baseline_heart_rate_above_personal_baseline`
- 是否出现 `window_repeated_tachycardia_30m`

### 测试 3：趋势 API

```powershell
..\.venv\Scripts\python manage.py generate_mock_monitoring_data --scenario trend --count 72 --interval-minutes 180 --username trend-user --device-id trend-ring-001
```

然后调用：

- `GET /api/v1/measurements/trends`

观察点：

- `daily`
- `weekly`
- `measurement_count`
- `high_risk_count`
- `alert_count`
- `avg_heart_rate`
- `avg_oxygen`

### 测试 4：LLM 解读接口

先生成一批高风险数据：

```powershell
..\.venv\Scripts\python manage.py generate_mock_monitoring_data --scenario high_risk --count 10 --interval-minutes 10 --username ai-user --device-id ai-ring-001
```

再取某条测量记录的 `id`，调用：

- `POST /api/v1/measurements/{measurement_id}/llm-insight`

如果 AI 设置是 `template`，你会看到稳定的模板化中文解释。

## 为什么这种方式适合当前项目

优点：

- 不依赖真实硬件
- 不依赖前端采集链路
- 可以快速重复测试
- 能同时覆盖解析、分析、趋势、告警、AI 解读

这非常适合：

- 后端联调
- 答辩前准备
- 演示环境快速造数

## 注意事项

### 1. 命令会不断追加数据

如果你多次执行同一组 `username + device_id`，会在原有数据上继续增加测量记录。

### 2. 建议使用专门的演示账号

例如：

- `risk-user`
- `trend-user`
- `ai-user`

这样更容易区分不同测试场景。

### 3. 推荐搭配管理员控制台查看

生成数据后，可在控制台查看：

- 测量页
- 告警页
- 趋势统计接口
- AI 设置页

## 总结

如果你要快速测试后端分析系统，最推荐的做法不是手工改数据库，而是使用：

- `generate_mock_monitoring_data`

它能让你低成本、高重复性地验证整个后端分析链路是否正常。
