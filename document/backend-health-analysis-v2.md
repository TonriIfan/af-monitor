# 后端健康分析 V2 设计说明

## 目标

在不引入 `PySpark` 等重型数据框架的前提下，将一期后端分析从“单次测量规则判断”升级为“单次规则 + 时间窗统计 + 个人基线偏移”的轻量分析方案。

该方案适合当前毕设阶段：

- 数据量较小，主要需求是在线 API 分析
- 需要结果可解释，便于答辩展示
- 需要在现有 Django 服务中快速落地

## 为什么不使用 PySpark

当前系统的核心是：

- 智能戒指上报数据接入
- 单次测量解析
- 风险评分
- 历史查询与告警

这属于在线业务链路，不属于超大规模离线批处理场景。`PySpark` 更适合：

- 海量历史数据离线聚合
- 批量特征工程
- 分布式训练或批量统计

当前阶段如果直接引入 `PySpark`，会明显增加部署和调试复杂度，但对实时 API 价值不大。

## 当前实现结构

核心文件：

- `backend/monitoring/services.py`

分析入口：

- `analyze_measurement(measurement)`

算法版本：

- `rules-window-baseline-v2`

## 分析结构

### 1. 实时规则层

基于当前一次测量直接判断：

- 心率过快
- 心率过慢
- HRV 异常偏高
- 压力过高
- 血氧偏低
- 体温偏高

如果同时出现“心动过速 + HRV 不稳定 + 低血氧”，会标记为更高风险的聚类异常。

### 2. 时间窗统计层

在最近 `30 分钟` 和 `24 小时` 范围内，统计重复异常：

- `window_repeated_tachycardia_30m`
- `window_repeated_low_oxygen_30m`
- `window_repeated_hrv_instability_30m`
- `window_repeated_high_risk_24h`

作用：

- 避免只看单条测量造成偶然误报
- 能体现“持续异常”而不是“瞬时异常”

### 3. 个人基线层

从最近 `7 天` 的历史测量中提取个人基线均值：

- 心率基线
- HRV 基线
- 血氧基线
- 体温基线

然后比较当前值是否明显偏离个人历史水平：

- `baseline_heart_rate_above_personal_baseline`
- `baseline_oxygen_below_personal_baseline`
- `baseline_hrv_above_personal_baseline`
- `baseline_temperature_above_personal_baseline`

作用：

- 不同用户共享固定阈值的问题会被缓解
- 更符合健康监测里“个体差异明显”的特点

### 4. 佩戴有效性修正

如果当前佩戴状态不稳定，系统会降低最终风险分数，并补充：

- `context_unstable_wear_state`

作用：

- 避免在无效佩戴状态下过度解读测量结果

## 输出结构

分析结果现在包含：

- `algorithm_version`
- `risk_level`
- `risk_score`
- `labels`
- `triggers`
- `details`
- `summary`
- `should_alert`

其中 `details` 是给前端、后续 AI 解读和论文展示使用的结构化信息，包含：

- `realtime_flags`
- `window_flags`
- `baseline_flags`
- `window_stats`
- `baselines`
- `wearing_effective`

## 风险等级说明

综合分数后映射为：

- `low`
- `moderate`
- `high`
- `critical`

当前仍然属于“异常心律风险预警/房颤风险筛查”逻辑，不应表述为临床确诊。

## 后续可继续增强的方向

### 1. 更稳的基线建模

当前使用均值，后续可以换成：

- 中位数
- 分位数
- 分时段基线（白天 / 夜间）

### 2. 更完整的时间序列特征

例如：

- 最近 1 小时异常比例
- 夜间异常次数
- 过去 7 天风险趋势

### 3. 轻量机器学习

在当前规则和统计特征基础上，后续可引入：

- `scikit-learn`
- `XGBoost`
- `LightGBM`

作为离线训练、在线推理的下一阶段演进。

## 结论

当前 V2 方案相比原先的单次规则判断，已经具备：

- 更强的可解释性
- 更合理的个体化判断
- 更稳定的连续异常识别能力

它仍然是轻量级实现，但已经更适合作为毕设后端分析核心。
