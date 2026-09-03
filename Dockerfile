FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py manillen_functions.py score_functions.py reserve_assignments.py github_publish.py ./
COPY mirror_app/__init__.py mirror_app/data_helpers.py mirror_app/score_helpers.py ./mirror_app/
COPY www/ ./www/
COPY data/ ./data-seed/
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["shiny", "run", "--host", "0.0.0.0", "--port", "8000", "app.py"]
