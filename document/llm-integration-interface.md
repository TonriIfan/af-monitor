# LLM 接口预留说明

## 目标

当前系统先完成传统规则分析与风险评分，但为后续接入 AI 解读能力预留统一接口。

设计原则：

- 不影响现有 API 主链路
- 默认不开启外部大模型调用
- 没有 API Key 时也能返回可用的上下文和 Prompt

## 当前实现

核心文件：

- `backend/monitoring/llm.py`
- `backend/monitoring/views.py`
- `backend/monitoring/urls.py`

接口：

- `POST /api/v1/measurements/{measurement_id}/llm-insight`

## 接口行为

### 默认状态

如果没有配置外部模型服务，接口会返回：

- `available: false`
- `prompt`
- `context`
- `provider`
- `model`

这样前端或后续服务可以先看到：

- 传给 LLM 的上下文是什么
- Prompt 是怎么组织的
- 后续需要什么配置才能真正调用模型

### 配置后状态

如果配置了兼容 OpenAI Chat Completions 的接口，后端会尝试真实调用，并返回：

- `available: true`
- `content`
- `context`
- `prompt`

## 环境变量

当前支持以下变量：

- `LLM_PROVIDER`
- `LLM_API_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `LLM_TIMEOUT`

推荐含义：

- `LLM_PROVIDER=openai_compatible`
- `LLM_API_BASE_URL=https://your-llm-service.example.com/v1`
- `LLM_MODEL=gpt-4o-mini`

如果不配置，系统默认为：

- `LLM_PROVIDER=disabled`

## 为什么先保留接口而不直接强依赖 LLM

原因有三点：

### 1. 先保证核心分析可控

当前规则分析、时间窗统计、个人基线偏移，是系统必须稳定可解释的核心逻辑。

### 2. 大模型适合做“解释层”而不是“主判定层”

房颤风险判断目前应以结构化规则/统计结果为主，LLM 更适合做：

- 风险解读
- 面向用户的中文说明
- 告警内容润色
- 健康建议生成

### 3. 接入方式以后可能变化

后续可以接：

- OpenAI 兼容接口
- 本地部署模型
- 医疗专用问答模型

因此现在先把接口层抽出来，比把模型调用写死在主分析逻辑里更稳。

## 推荐使用方式

建议未来把 LLM 作为“辅助解读模块”，而不是直接替代规则分析：

1. 先由后端规则分析输出结构化结果
2. 再把结构化结果传给 LLM
3. 由 LLM 输出更适合用户阅读的中文解释

推荐输出结构：

- 风险结论
- 触发原因
- 建议动作
- 注意事项

## 当前接口的价值

虽然现在默认不调用真实大模型，但这个接口已经具备：

- 稳定的输入输出形态
- 可调试的 Prompt
- 后续可直接接入 AI 服务的扩展位

这意味着后续接入 AI 时，不需要再改动主分析链路，只需要补环境变量和服务地址即可。
