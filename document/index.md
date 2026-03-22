---
layout: home

hero:
  name: "HeartGuard Docs"
  text: "房颤监测后端与 API 文档站"
  tagline: "面向前端、App、后端联调与部署的统一文档入口"
  actions:
    - theme: brand
      text: 查看 App API
      link: /app-api-reference
    - theme: alt
      text: 查看前端 API
      link: /frontend-api-reference
    - theme: alt
      text: 查看部署文档
      link: /nginx-and-production-deploy

features:
  - title: App 对接
    details: 覆盖注册、登录、资料、首页摘要、趋势、报告、AI 问答和离线批量上报。
    link: /app-api-reference
  - title: Web / Console 对接
    details: 详细说明 Token、管理员视角、设备、测量、告警、AI 设置和 `user_id` 作用域切换。
    link: /frontend-api-reference
  - title: 分析与 AI
    details: 说明规则 + 时间窗 + 个人基线分析，AI 接口与模板/外部 LLM 接入方式。
    link: /backend-health-analysis-v2
  - title: 测试与造数
    details: 使用虚拟监测数据快速验证解析、分析、趋势、告警和 AI 解读链路。
    link: /mock-data-testing
  - title: 部署上线
    details: 覆盖域名规划、跨域、HTTPS、Nginx、控制台和 API 生产部署方式。
    link: /nginx-and-production-deploy
---

## 文档结构

- API 文档
  - [App API 对接文档](/app-api-reference)
  - [App 注册接口说明](/app-registration-api)
  - [前端接口对接手册](/frontend-api-reference)
- 分析与 AI
  - [后端健康分析 v2](/backend-health-analysis-v2)
  - [LLM 接口说明](/llm-integration-interface)
  - [趋势接口与 AI 设置](/trend-api-and-ai-settings)
  - [AI 设置测试](/ai-settings-test)
  - [虚拟数据测试说明](/mock-data-testing)
- 部署
  - [域名与跨域配置](/domain-and-cors-setup)
  - [Nginx 与生产部署](/nginx-and-production-deploy)
  - [VitePress 文档站说明](/vitepress-doc-site)

## 部署目标

当前文档站已经按下面的访问方式配置：

- 文档站基础路径：`/docs/`
- 目标访问地址：`https://api.heartguard.cn/docs`

这意味着静态构建时已经考虑了：

- VitePress `base = /docs/`
- 适合交给 Nginx 挂在 `api.heartguard.cn/docs`

## 本地运行

```powershell
cd yf-monitor\document
npm install
npm run docs:dev
```

生产构建：

```powershell
cd yf-monitor\document
npm run docs:build
```
