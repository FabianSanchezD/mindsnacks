import uvicorn
from fastapi.staticfiles import StaticFiles
from mindsnacks_backend import app
import os
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---- Initialization: Create required files and directories ----
logger.info("Initializing application directories and files")
os.makedirs("static/audio", exist_ok=True)

# Initialize required files with proper structure
required_files = {
    "user_history.json": [],
    "user_topic_history.json": [],
    "topic_cache.json": {
        "timestamp": "",
        "topics": {}
    }
}

for filename, default_content in required_files.items():
    if not os.path.exists(filename):
        logger.info(f"Creating file: {filename}")
        with open(filename, "w") as f:
            json.dump(default_content, f)
    else:
        # Validate file content is proper JSON
        try:
            with open(filename, "r") as f:
                content = f.read().strip()
                if not content:
                    # Write default content if file is empty
                    with open(filename, "w") as f:
                        json.dump(default_content, f)
                else:
                    # Try to parse as JSON to validate
                    json.loads(content)
        except json.JSONDecodeError:
            logger.warning(f"File {filename} contains invalid JSON. Resetting to default.")
            with open(filename, "w") as f:
                json.dump(default_content, f)
        except Exception as e:
            logger.error(f"Error processing file {filename}: {e}")
