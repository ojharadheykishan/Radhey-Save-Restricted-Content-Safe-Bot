FROM python:3.10-slim-bullseye

# Make apt tolerant to expired/changed release metadata (Bullseye security files sometimes expire)
# Try a normal update, fall back to --allow-releaseinfo-change if available, then upgrade.
RUN set -eux; \
	apt-get update || apt-get update --allow-releaseinfo-change || apt-get update --allow-releaseinfo-change=1 || true; \
	apt-get -y upgrade; \
	apt-get install -y --no-install-recommends git curl ffmpeg wget bash neofetch ca-certificates; \
	rm -rf /var/lib/apt/lists/*;

COPY requirements.txt .

RUN pip3 install wheel
RUN pip3 install --no-cache-dir -U -r requirements.txt
WORKDIR /app
COPY . .

CMD ["python3", "app.py"]


