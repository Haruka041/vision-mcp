import subprocess
import sys
import signal
import atexit

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

    try:
        run()
    finally:
        cleanup()


if __name__ == "__main__":
    main()
