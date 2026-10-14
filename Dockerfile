FROM python:3.11-slim

WORKDIR /code

COPY backend/requirements.txt /code/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/backend/requirements.txt

COPY backend /code/backend
COPY frontend/dist /code/frontend/dist
RUN mkdir -p /code/data

EXPOSE 8000

ENV PORT=8000
ENV HOST=0.0.0.0
ENV PYTHONPATH=/code/backend

CMD ["python", "backend/server.py"]
