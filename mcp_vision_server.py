import sqlite3
import time
import base64
import urllib.request
import os
from pathlib import Path
from openai import OpenAI
from mcp.server.fastmcp import FastMCP

DB_PATH = Path("/data/mcp_management.db")

mcp = FastMCP("mcp-vision-server")


def get_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            openai_api_key TEXT DEFAULT '',
            openai_base_url TEXT DEFAULT 'https://api.openai.com/v1',
            vision_model TEXT DEFAULT 'gpt-4o'
        );
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT (datetime('now','localtime')),
            prompt TEXT,
            image_size INTEGER DEFAULT 0,
            duration_ms REAL DEFAULT 0,
            response_text TEXT DEFAULT '',
            error_message TEXT DEFAULT '',
            status TEXT DEFAULT 'success'
        );
        INSERT OR IGNORE INTO settings (id) VALUES (1);
    """)
    conn.commit()
    conn.close()


def get_settings():
    conn = get_db()
    row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return {"openai_api_key": "", "openai_base_url": "https://api.openai.com/v1", "vision_model": "gpt-4o"}
    return dict(row)


def log_call(prompt, image_size, duration_ms, response_text="", error_message="", status="success"):
    conn = get_db()
    conn.execute(
        """INSERT INTO logs (timestamp, prompt, image_size, duration_ms, response_text, error_message, status)
           VALUES (datetime('now','localtime'), ?, ?, ?, ?, ?, ?)""",
        (prompt, image_size, duration_ms, response_text, error_message, status)
    )
    conn.commit()
    conn.close()


def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
    today = conn.execute(
        "SELECT COUNT(*) FROM logs WHERE date(timestamp) = date('now','localtime')"
    ).fetchone()[0]
    conn.close()
    return {"total_calls": total, "today_calls": today}


def get_image_bytes(image_input: str) -> bytes:
    # 1. Check if it's http/https URL
    if image_input.startswith(("http://", "https://")):
        req = urllib.request.Request(
            image_input,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read()

    # 2. Check if it's file:// URL or local path
    elif image_input.startswith("file://"):
        path = image_input[7:]
        # Remove leading slash on windows if necessary, e.g. /C:/Users/...
        if os.name == 'nt' and path.startswith("/") and path[2] == ':':
            path = path[1:]
        with open(path, "rb") as f:
            return f.read()

    elif "/" in image_input or "\\" in image_input or image_input.endswith((".png", ".jpg", ".jpeg", ".webp")):
        # Treat as local path directly
        with open(image_input, "rb") as f:
            return f.read()

    else:
        # Assume it's already base64 data
        # Clean prefix if present
        if "," in image_input:
            image_input = image_input.split(",")[-1]
        return base64.b64decode(image_input)


@mcp.tool()
def analyze_image_bytes(image_base64: str, prompt: str = "请描述这张图片中的内容") -> str:
    settings = get_settings()
    api_key = settings.get("openai_api_key", "")
    base_url = settings.get("openai_base_url", "https://api.openai.com/v1")
    model = settings.get("vision_model", "gpt-4o")

    image_size = len(image_base64)
    start = time.time()

    try:
        # Resolve path, URL, or decode base64
        image_data = get_image_bytes(image_base64)
        base64_data = base64.b64encode(image_data).decode('utf-8')
        
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_data}"}}
                ]
            }],
            max_tokens=4096
        )
        result = response.choices[0].message.content
        duration_ms = round((time.time() - start) * 1000, 2)
        log_call(prompt, image_size, duration_ms, response_text=result)
        return result
    except Exception as e:
        duration_ms = round((time.time() - start) * 1000, 2)
        error_msg = str(e)
        
        # If it failed to read local path, return a helpful friendly warning to user/LLM
        if isinstance(e, (FileNotFoundError, OSError)):
            friendly_err = (
                f"无法读取图片内容 (错误: {error_msg})。 "
                f"特别提示：若您的 MCP 服务部署在 Docker 容器或远程服务器中，它将无法直接读取您本地电脑上的文件 ({image_base64})。 "
                f"请尝试将图片上传到网络图床/局域网 Web，并把 http:// 或 https:// 图片链接直接提供给模型进行识别；"
                f"或者将本 MCP 服务在本地电脑（直接使用 Python 运行）进行部署。"
            )
            log_call(prompt, image_size, duration_ms, error_message=friendly_err, status="failed")
            return friendly_err
            
        log_call(prompt, image_size, duration_ms, error_message=error_msg, status="failed")
        return f"Error: {error_msg}"


def run():
    init_db()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
