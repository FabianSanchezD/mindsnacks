import uvicorn
from fastapi.staticfiles import StaticFiles
from mindsnacks_backend import app

# Mount static directory for serving audio files
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
