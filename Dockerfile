FROM python:3.11-buster
WORKDIR /server

COPY python/requirements.txt .
RUN pip install -r requirements.txt

COPY python  .
CMD ["python", "-u", "server.py"]
