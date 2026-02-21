import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "Backend")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import create_app, init_db  # noqa: E402

config_name = os.environ.get("APP_CONFIG", "production")
app = create_app(config_name)
init_db(app)
