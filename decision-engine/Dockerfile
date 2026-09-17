FROM python:3.12-slim

WORKDIR /app

# curl is used by the chart's lifecycle hooks to register and remove the
# event subscription on the 5G core; tini reaps the threads Flask spawns.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl tini \
    && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

EXPOSE 8880

ENTRYPOINT ["/usr/bin/tini", "--", "python", "decision_engine.py"]
