import uvicorn
from fastapi.staticfiles import StaticFiles
from mindsnacks_backend import app

import os
import json

# ---- Initialization: Create required files if they don't exist ----
os.makedirs("static/audio", exist_ok=True)

for filename in ["user_history.json", "topic_cache.json", "user_topic_history.json"]:
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            json.dump({}, f)


# Mount static directory for serving audio files
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
