# MCP Vision Server (多模态识图与管理后台双引擎版)

这是一个功能强大的多模态 MCP (Model Context Protocol) 识图服务。它创新地采用了**双引擎运行架构**，在同一个 Docker 容器内同时启动了：
1. **MCP 识图服务**：通过标准输入输出 (stdio) 与大模型客户端（如 OpenCode, Claude Desktop 等）无缝通信。
2. **Web 后端管理服务**：暴露 `8080` 端口，提供极简、美观的单页面 UI，供用户实时配置大模型连接参数、查看使用次数、统计看板及详细调用/报错日志。

---

## 🌟 核心特性
- **双引擎并发**：通过精细的信号与进程处理，既可响应客户端识图，又可同时提供网页后台服务。
- **动态配置**：无需重启 Docker 容器。在网页端修改 API Key、Base URL 或 Model Name，配置将立即保存到 SQLite 数据库并应用到下一次识图调用中。
- **完整的日志监控**：记录每次识图调用的时间、用户 Prompt、图片大小、接口耗时、模型返回结果及成功/失败状态。若调用失败，提供醒目的红色错误日志展示。
- **Gemini / OpenAI 完美适配**：支持标准 OpenAI 多模态接口，并且天然兼容 Gemini 的 OpenAI 兼容模式。

---

## 🛠 编译与运行指南

### 1. 本地手动构建与启动
在项目根目录下执行以下命令构建 Docker 镜像：
```bash
docker build -t mcp-vision-server .
```

#### A. 供 MCP 客户端直接调用（推荐，双引擎运行）
在 OpenCode 或 Claude Desktop 客户端配置文件（如 `claude_desktop_config.json`）中添加该 MCP 服务。**必须指定 `-i`（交互模式）以及挂载持久化数据库目录**：

```json
{
  "mcpServers": {
    "mcp-vision-server": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-p", "8080:8080",
        "-v", "F:/MCP/mcp_data:/data",
        "mcp-vision-server"
      ]
    }
  }
}
```
*注：请将 `F:/MCP/mcp_data` 替换为您本地用于存放数据库的真实绝对路径。*

#### B. 独立运行 Web 调试模式
如果您仅需要启动 Web 管理后台测试：
```bash
docker run -d \
  -p 8080:8080 \
  -v ./mcp_data:/data \
  --name mcp-vision \
  mcp-vision-server
```

---

## ⚙️ 模型配置说明 (以 Gemini 为例)

打开浏览器，访问管理后台 `http://localhost:8080`，在【模型配置】中填写：
* **Base URL**: `https://generativelanguage.googleapis.com/v1beta/openai/`
* **API Key**: 填入您的 Google AI Studio API Key
* **模型名称**: `gemini-2.5-flash` 或 `gemini-2.0-flash`
* （若使用第三方中转服务如 OpenRouter，可将 Base URL 设为 `https://openrouter.ai/api/v1`，模型设为相应的视觉模型标识符）

保存配置后立即生效，下一次识图会自动使用最新的配置进行调用。

---

## 🚀 GitHub Actions 与 GHCR 自动分发

项目已配置 GitHub Actions 自动流。当您将代码开源至 GitHub 并推送至 `main` 分支或打 `v*` 版本标签时：
1. GitHub Actions 会自动触发构建工作流。
2. 构建出的 Docker 镜像会自动发布至 GitHub 容器注册表 (GHCR)。
3. 其他用户或您自己在服务器上，只需通过以下命令即可拉取并运行最新镜像：

```bash
docker pull ghcr.io/<你的GitHub用户名>/<仓库名>:latest
```
