# 设备协议整理

基于当前微信小程序 `study/ble/pages/index/index.js` 的解析逻辑整理。

## 已支持命令

| 命令 | 子命令 | 含义 | 解析字段 |
| --- | --- | --- | --- |
| `0x12` | `0x00` | 查询电量 | `batteryLevel` |
| `0x12` | `0x01` | 查询充电状态 | `batteryState` |
| `0x10` | `0x00` | 时间同步结果 | `isSyncTime` |
| `0x10` | `0x01` | 设备时间读取 | `ringTime`, `timezone` |
| `0x31` | `0x00` | 心率/HRV/压力/体温联合测量 | `wearStatusText`, `heartRate`, `hrv`, `stress`, `temperature` |
| `0x32` | `0x00` | 血氧测量 | `oxygenWearStatusText`, `oxygenHeartRate`, `oxygen`, `oxygenTemperature` |
| `0x32` | `0xFF` | 血氧采集完成 | `oxygenWearStatusText` |
| `0x34` | `0x00` | 体温测量 | `StatusText`, `TempTest` |

## 状态码

### 佩戴状态

- `0`: 未佩戴
- `1`: 佩戴
- `2`: 充电中不允许采集
- `3`: 采集中
- `4`: 繁忙不执行

### 电池状态

- `0`: 未充电
- `1`: 充电中
- `2`: 充满

### 体温测量状态

- `0`: 测量中
- `1`: 测量完成
- `2`: 测量失败并结束
- `3`: 繁忙，不执行

## 上报 JSON

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

约束：
- `payload` 原样保存到 `raw_payload`
- 后端只新增 `parsed`、`analysis`、`alert_state`
- 当 `frame_hex` 与 `frame_bytes` 只提供其一时，后端会补全另一种表示
