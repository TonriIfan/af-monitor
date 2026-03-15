import { defineConfig } from 'vitepress'

export default defineConfig({
  lang: 'zh-CN',
  title: 'HeartGuard Docs',
  description: 'HeartGuard 后端 API、分析系统与部署文档',
  base: '/docs/',
  cleanUrls: true,
  lastUpdated: true,
  themeConfig: {
    logo: '/logo.svg',
    siteTitle: 'HeartGuard Docs',
    nav: [
      { text: '首页', link: '/' },
      { text: 'App API', link: '/app-api-reference' },
      { text: '前端 API', link: '/frontend-api-reference' },
      { text: '部署', link: '/nginx-and-production-deploy' },
    ],
    sidebar: [
      {
        text: '开始',
        items: [
          { text: '文档首页', link: '/' },
          { text: 'VitePress 文档站说明', link: '/vitepress-doc-site' },
        ],
      },
      {
        text: 'API 文档',
        items: [
          { text: 'App API 对接文档', link: '/app-api-reference' },
          { text: 'App 注册接口说明', link: '/app-registration-api' },
          { text: '前端接口对接手册', link: '/frontend-api-reference' },
        ],
      },
      {
        text: '分析与 AI',
        items: [
          { text: '后端健康分析 v2', link: '/backend-health-analysis-v2' },
          { text: 'LLM 接口说明', link: '/llm-integration-interface' },
          { text: '趋势接口与 AI 设置', link: '/trend-api-and-ai-settings' },
          { text: 'AI 设置测试', link: '/ai-settings-test' },
          { text: '虚拟数据测试说明', link: '/mock-data-testing' },
        ],
      },
      {
        text: '部署',
        items: [
          { text: '域名与跨域配置', link: '/domain-and-cors-setup' },
          { text: 'Nginx 与生产部署', link: '/nginx-and-production-deploy' },
        ],
      },
    ],
    socialLinks: [
      { icon: 'github', link: 'https://github.com/OpenHealthForAll/open-health' },
    ],
    footer: {
      message: 'HeartGuard Documentation',
      copyright: 'Copyright © 2026 HeartGuard',
    },
    search: {
      provider: 'local',
    },
    outline: {
      level: [2, 3],
    },
  },
})
