FROM python:3.12.8-slim-bookworm
RUN useradd --create-home --uid 1000 agent
WORKDIR /app
COPY store.py /app/store.py
RUN chown -R agent:agent /app
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["sleep", "infinity"]
