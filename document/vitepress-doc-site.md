# VitePress 文档站说明

## 目标

当前 `document` 目录已经被整理为一个可直接构建的 VitePress 文档站。

部署目标是：

- `https://api.heartguard.cn/docs`

因此当前文档站配置中：

- `base = /docs/`

## 目录结构

当前结构如下：

```text
document/
  .vitepress/
    config.mts
    theme/
      index.ts
      custom.css
  index.md
  package.json
  *.md
```

说明：

- 现有业务文档继续保留在 `document/*.md`
- VitePress 直接把这些 md 文件当页面
- 不需要额外复制到别的目录

## 运行方式

### 本地开发

```powershell
cd yf-monitor\document
npm install
npm run docs:dev
```

默认会启动一个本地文档站。

### 生产构建

```powershell
cd yf-monitor\document
npm run docs:build
```

构建产物目录为：

```text
document/.vitepress/dist
```

## 部署到 `api.heartguard.cn/docs`

推荐用 Nginx 把静态产物挂在 `/docs/`。

示例：

```nginx
location /docs/ {
    alias /srv/heartguard/document-dist/;
    index index.html;
    try_files $uri $uri/ /docs/index.html;
}
```

注意点：

- 这里是 `alias`，不是 `root`
- 回退路径要写成 `/docs/index.html`
- 因为 VitePress 已经配置 `base = /docs/`，资源路径会自动带上 `/docs/`

## 推荐部署流程

1. 在本地或服务器执行：

```bash
cd /srv/heartguard/document
npm install
npm run docs:build
```

2. 将构建结果放到：

```text
/srv/heartguard/document-dist
```

3. 在 `api.heartguard.cn` 的 Nginx 配置里增加 `/docs/` location

4. 重载 Nginx

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 当前文档导航

当前文档站已整理为这些主要栏目：

- 首页
- App API
- 前端 API
- 分析与 AI
- 测试与造数
- 域名与部署

## 为什么挂在 `api.heartguard.cn/docs`

你当前已经把：

- `api.heartguard.cn`

作为后端域名使用。

把文档挂到：

- `api.heartguard.cn/docs`

有几个现实好处：

- 前端联调人员只记一个后端域名
- API 和文档天然放在一起
- 不需要额外再申请一个 docs 子域名

如果后面你觉得需要把文档和 API 完全隔离，也可以再迁移到：

- `docs.heartguard.cn`

但当前阶段挂在 `/docs` 下已经足够合理。
