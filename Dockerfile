FROM python:3.10-slim-bullseye
RUN apt update && apt upgrade -y
RUN apt-get install -y git curl ffmpeg wget bash neofetch procps
COPY requirements.txt .

RUN pip3 install wheel
RUN pip3 install --no-cache-dir -U -r requirements.txt
WORKDIR /app
COPY . .

# Make process manager executable
RUN chmod +x process_manager.py

# Use process manager to ensure both processes run continuously
CMD python3 process_manager.py

