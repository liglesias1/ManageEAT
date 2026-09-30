"""All runtime configuration comes from environment variables, with safe defaults."""
import os
from pathlib import Path

HOST = "0.0.0.0" #to allow access from outside the computer.
PORT = int(os.getenv("PORT", "8000")) #si no existe variable PORT, usa 8000.

BASE_DIR = Path(__file__).resolve().parent #ruta del directorio base
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data")) #ruta del directorio de datos

DB_PATH = DATA_DIR / "manageeat.db" #ruta de la base de datos

# If true, the app fills an empty database with demo data on startup.
SEED_DEMO_DATA = os.getenv("SEED_DEMO_DATA", "true").lower() == "true"