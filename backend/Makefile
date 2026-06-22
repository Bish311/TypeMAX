.PHONY: api worker load start-all

# Start the FastAPI web server
api:
	.\venv\Scripts\uvicorn server_routing:app --reload --port 8765

# Start the background batch processor
worker:
	.\venv\Scripts\python batch_processor.py

# Ingest the 100k queries dataset (Run this once)
load:
	.\venv\Scripts\python data_loader.py

# Start both the web server and background worker in separate windows (Windows specific)
start-all:
	start .\venv\Scripts\uvicorn server_routing:app --reload
	start .\venv\Scripts\python batch_processor.py
