FROM python:3.11-slim

WORKDIR /code

COPY backend/requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY backend /code

EXPOSE 7860

ENV PORT=7860
ENV HOST=0.0.0.0

CMD ["python", "server.py"]
