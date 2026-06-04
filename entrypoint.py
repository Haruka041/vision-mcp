import subprocess
import sys
import signal
import atexit
import time

web = None


def cleanup():
    global web
    if web and web.poll() is None:
        web.terminate()
        try:
            web.wait(timeout=5)
        except subprocess.TimeoutExpired:
            web.kill()


def signal_handler(signum, frame):
    cleanup()
    sys.exit(0)


def main():
    global web
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    atexit.register(cleanup)

    # Initialize database first so both processes see it initialized
    from mcp_vision_server import init_db, run
    init_db()

    # Redirect stdout to DEVNULL to prevent interfering with MCP stdio, but redirect stderr to container stderr for logging
    web = subprocess.Popen(
        ["uvicorn", "web_server:app", "--host", "0.0.0.0", "--port", "8080"],
        stdout=subprocess.DEVNULL,
        stderr=sys.stderr
    )

    start_time = time.time()
    try:
        run()
    except Exception as e:
        sys.stderr.write(f"MCP server exited: {e}\n")

    elapsed = time.time() - start_time
    if elapsed < 3.0:
        sys.stderr.write("MCP server exited immediately (likely running in detached/daemon mode). Keeping container alive for Web UI...\n")
        if web.poll() is None:
            try:
                web.wait()
            except KeyboardInterrupt:
                cleanup()
    else:
        cleanup()


if __name__ == "__main__":
    main()
