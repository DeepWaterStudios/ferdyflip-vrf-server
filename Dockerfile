FROM python:3.11-slim-buster
WORKDIR /server

COPY python/requirements.txt .
RUN pip install -r requirements.txt

COPY python  .
# RUN rm /server/.env*

CMD ["python", "-u", "server.py"]
