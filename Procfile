web: gunicorn --workers 1 src.app:app
collector: python -m src.collector_worker --interval-seconds 3600
analyzer: python -m src.consumer
