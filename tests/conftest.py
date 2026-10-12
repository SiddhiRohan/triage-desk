import pytest
import os

@pytest.fixture(autouse=True)
def db_path(tmp_path):
    # Create a temporary database path
    db_file = tmp_path / "test_triage.db"
    db_path_str = str(db_file)
    
    # Set the environment variable for the app to use
    os.environ["DB_PATH"] = db_path_str
    
    # Import init_db here to ensure it uses the updated DB_PATH
    from app.db import init_db
    init_db()
    
    return db_path_str
