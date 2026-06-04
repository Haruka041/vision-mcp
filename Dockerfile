FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir mcp mcp[cli] openai fastapi uvicorn

COPY mcp_vision_server.py web_server.py entrypoint.py /app/

RUN mkdir -p /data

EXPOSE 8080

ENTRYPOINT ["python", "entrypoint.py"]
