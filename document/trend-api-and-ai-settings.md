# 趋势统计 API 与 AI 设置说明

## 1. 日/周趋势统计 API

### 接口

- `GET /api/v1/measurements/trends`

### 作用

用于给后端、控制台或后续 App 提供近阶段健康趋势数据，而不是只看单次测量。

### 权限与作用域

- 普通用户：查看自己的趋势
- 管理员：默认查看所有普通用户趋势
- 管理员传 `user_id` 时：查看指定普通用户趋势

### 返回结构

接口返回两个维度：

- `daily`
- `weekly`

每个时间桶包含：

- `label`
- `measurement_count`
- `high_risk_count`
- `alert_count`
- `avg_heart_rate`
- `avg_oxygen`

### 设计取舍

当前实现使用 Django 查询 + Python 聚合，不依赖额外分析框架。

这样做的原因：

- 当前数据规模不大
- 在线 API 需要简单稳定
- SQLite 和 MySQL 都能直接运行

## 2. AI 设置 API

### 接口

- `GET /api/v1/ai/settings`
- `PUT /api/v1/ai/settings`

### 作用

给管理员提供统一的 AI 配置入口，而不是把 AI 参数散落在代码和环境变量里。

### 当前支持字段

- `enabled`
- `mode`
- `api_base_url`
- `api_key`
- `model`
- `temperature`
- `system_prompt`

### 模式说明

- `disabled`
  接口存在，但不视为启用 AI

- `template`
  不调用外部模型，直接返回模板化中文解释

- `openai_compatible`
  调用兼容 OpenAI Chat Completions 的外部模型，失败时自动回退模板解释

## 3. LLM 解读接口

### 接口

- `POST /api/v1/measurements/{measurement_id}/llm-insight`

### 返回策略

无论是否配置外部模型，接口都会返回：

- `content`
- `template_content`
- `context`
- `prompt`
- `source`

### source 说明

- `template`
  当前使用模板解释

- `llm`
  当前使用外部大模型解释

- `template_fallback`
  原本尝试调用外部大模型，但失败后回退到模板解释

## 4. 模板化解释为什么要保留

原因很简单：

- 毕设演示不能依赖外部接口一定可用
- 健康解读必须先有稳定兜底
- 模板解释足以支撑一期的中文风险说明

因此当前策略是：

1. 规则分析先产出结构化结果
2. 模板解释负责“面向患者的中文说明”
3. 配置真实模型后，再让 LLM 替代模板内容

## 5. Console 中的 AI 设置页面

控制台新增管理员页面：

- `http://localhost:5173/ai-settings`

用途：

- 开关 AI 解读
- 选择模式
- 配置兼容 OpenAI 的模型地址与 Key
- 调整模型名和温度
- 自定义系统提示词

## 6. 推荐使用方式

当前阶段建议：

- 默认启用 `template`
- 当你准备接真实 AI 服务时，再切到 `openai_compatible`

这样可以兼顾：

- 稳定性
- 演示效果
- 后续扩展性
