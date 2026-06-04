from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
from pathlib import Path
from mcp_vision_server import mcp

# Disable DNS rebinding protection for internal network SSE support
mcp.settings.transport_security.enable_dns_rebinding_protection = False

DB_PATH = Path("/data/mcp_management.db")

app = FastAPI(title="MCP Vision Manager")

# Enable CORS for maximum compatibility (e.g. browser clients, external tools)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the MCP SSE Starlette app onto FastAPI
# Do NOT pass mount_path to sse_app() — FastAPI's Mount sets root_path automatically,
# which SseServerTransport uses to construct the correct message endpoint URL.
app.mount("/mcp", mcp.sse_app())


def get_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


class SettingsUpdate(BaseModel):
    openai_api_key: str
    openai_base_url: str
    vision_model: str


@app.get("/api/settings")
def get_settings():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            openai_api_key TEXT DEFAULT '',
            openai_base_url TEXT DEFAULT 'https://api.openai.com/v1',
            vision_model TEXT DEFAULT 'gpt-4o'
        );
        INSERT OR IGNORE INTO settings (id) VALUES (1);
    """)
    row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return {"openai_api_key": "", "openai_base_url": "https://api.openai.com/v1", "vision_model": "gpt-4o"}
    return dict(row)


@app.post("/api/settings")
def update_settings(data: SettingsUpdate):
    conn = get_db()
    conn.execute(
        "UPDATE settings SET openai_api_key=?, openai_base_url=?, vision_model=? WHERE id=1",
        (data.openai_api_key, data.openai_base_url, data.vision_model)
    )
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.get("/api/logs")
def get_logs(limit: int = Query(default=100, le=500)):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/stats")
def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
    today = conn.execute(
        "SELECT COUNT(*) FROM logs WHERE date(timestamp) = date('now','localtime')"
    ).fetchone()[0]
    conn.close()
    return {"total_calls": total, "today_calls": today}


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(HTML_PAGE)


HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MCP 多模态识图管理</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
</head>
<body class="bg-gray-100 min-h-screen">
<div id="app" class="container mx-auto p-6 max-w-6xl">
  <h1 class="text-3xl font-bold text-gray-800 mb-6 flex items-center gap-2">
    MCP 多模态识图管理
  </h1>

  <!-- Stats Dashboard -->
  <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
    <div class="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 text-center">
      <div class="text-5xl font-bold text-blue-600">{{ stats.total_calls }}</div>
      <div class="text-gray-500 mt-2 text-lg">总调用次数</div>
    </div>
    <div class="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 text-center">
      <div class="text-5xl font-bold text-emerald-600">{{ stats.today_calls }}</div>
      <div class="text-gray-500 mt-2 text-lg">今日调用次数</div>
    </div>
  </div>

  <!-- Settings Panel -->
  <div class="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 mb-6">
    <h2 class="text-xl font-semibold text-gray-800 mb-5 flex items-center gap-2">
      模型配置
    </h2>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-5 mb-5">
      <div>
        <label class="block text-sm font-medium text-gray-600 mb-1.5">Base URL</label>
        <input v-model="settings.openai_base_url"
               class="w-full border border-gray-300 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
               placeholder="https://api.openai.com/v1">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-600 mb-1.5">API Key</label>
        <input v-model="settings.openai_api_key"
               class="w-full border border-gray-300 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
               type="password" placeholder="sk-...">
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-600 mb-1.5">模型名称</label>
        <input v-model="settings.vision_model"
               class="w-full border border-gray-300 rounded-xl px-4 py-2.5 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
               placeholder="gpt-4o / gemini-2.0-flash-001">
      </div>
    </div>
    <div class="flex items-center gap-4">
      <button @click="saveSettings"
              class="bg-blue-600 hover:bg-blue-700 text-white font-medium px-6 py-2.5 rounded-xl transition-colors">
        保存配置
      </button>
      <span v-if="saveMsg" class="text-emerald-600 font-medium">{{ saveMsg }}</span>
    </div>
  </div>

  <!-- Logs Table -->
  <div class="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
    <h2 class="text-xl font-semibold text-gray-800 mb-5">调用日志</h2>
    <div class="overflow-auto max-h-96 rounded-xl border border-gray-200">
      <table class="w-full text-sm">
        <thead class="bg-gray-50 sticky top-0">
          <tr>
            <th class="px-4 py-3 text-left text-gray-600 font-medium">时间</th>
            <th class="px-4 py-3 text-left text-gray-600 font-medium">Prompt</th>
            <th class="px-4 py-3 text-left text-gray-600 font-medium">图片大小</th>
            <th class="px-4 py-3 text-left text-gray-600 font-medium">耗时(ms)</th>
            <th class="px-4 py-3 text-left text-gray-600 font-medium">状态</th>
            <th class="px-4 py-3 text-left text-gray-600 font-medium">响应 / 错误</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          <tr v-for="log in logs" :key="log.id"
              :class="log.status === 'failed' ? 'bg-red-50' : 'hover:bg-gray-50'">
            <td class="px-4 py-3 whitespace-nowrap text-gray-600">{{ log.timestamp }}</td>
            <td class="px-4 py-3 max-w-xs truncate text-gray-800">{{ log.prompt }}</td>
            <td class="px-4 py-3 text-gray-600">{{ formatSize(log.image_size) }}</td>
            <td class="px-4 py-3 text-gray-600">{{ log.duration_ms }}</td>
            <td class="px-4 py-3">
              <span v-if="log.status === 'failed'"
                    class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                失败
              </span>
              <span v-else
                    class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                成功
              </span>
            </td>
            <td class="px-4 py-3 max-w-md truncate"
                :class="log.status === 'failed' ? 'text-red-600' : 'text-gray-700'">
              {{ log.status === 'failed' ? log.error_message : log.response_text }}
            </td>
          </tr>
          <tr v-if="logs.length === 0">
            <td colspan="6" class="px-4 py-10 text-center text-gray-400">暂无调用日志，使用 MCP 识图功能后数据将自动显示</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<script>
const { createApp, ref, onMounted } = Vue;

createApp({
  setup() {
    const settings = ref({ openai_api_key: '', openai_base_url: 'https://api.openai.com/v1', vision_model: 'gpt-4o' });
    const logs = ref([]);
    const stats = ref({ total_calls: 0, today_calls: 0 });
    const saveMsg = ref('');

    async function fetchData() {
      try {
        const [s, l, st] = await Promise.all([
          fetch('/api/settings').then(r => r.json()),
          fetch('/api/logs').then(r => r.json()),
          fetch('/api/stats').then(r => r.json()),
        ]);
        settings.value = s;
        logs.value = l;
        stats.value = st;
      } catch (e) {
        console.error('Failed to fetch data', e);
      }
    }

    async function saveSettings() {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings.value)
      });
      saveMsg.value = '配置已保存，更改立即生效';
      setTimeout(() => { saveMsg.value = ''; }, 3000);
    }

    function formatSize(bytes) {
      if (!bytes || bytes === 0) return '0 B';
      const kb = bytes / 1024;
      if (kb > 1024) return (kb / 1024).toFixed(1) + ' MB';
      return kb.toFixed(1) + ' KB';
    }

    onMounted(fetchData);

    return { settings, logs, stats, saveMsg, saveSettings, formatSize };
  }
}).mount('#app');
</script>
</body>
</html>
"""
