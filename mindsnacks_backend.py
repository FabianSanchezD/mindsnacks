from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import openai
import requests
import os
import uuid

app = FastAPI()

# Load API keys from environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

class EpisodeRequest(BaseModel):
    topics: List[str]
    num_episodes: int = 6

class EpisodeResponse(BaseModel):
    title: str
    description: str
    audio_url: str

@app.post("/generate", response_model=List[EpisodeResponse])
def generate_episodes(req: EpisodeRequest):
    try:
        topics_text = ", ".join(req.topics)
        prompt = f"Create {req.num_episodes} educational scripts (~5 minutes each) on these topics: {topics_text}. Return each with a title and a ~5 sentence description."

        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a brilliant educational podcaster who creates clear, engaging 5-minute scripts."},
                {"role": "user", "content": prompt}
            ]
        )

        generated_text = response.choices[0].message['content']
        snippets = generated_text.split("\n\n")

        results = []

        for i, snippet in enumerate(snippets):
            if not snippet.strip():
                continue

            tts_response = requests.post(
                "https://api.elevenlabs.io/v1/text-to-speech/eleven_monolingual_v1",
                headers={
                    "xi-api-key": ELEVENLABS_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "text": snippet,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
                }
            )

            if tts_response.status_code != 200:
                raise HTTPException(status_code=500, detail="TTS generation failed")

            audio_filename = f"mindsnacks_episode_{uuid.uuid4().hex[:8]}.mp3"
            audio_path = f"static/audio/{audio_filename}"

            os.makedirs("static/audio", exist_ok=True)
            with open(audio_path, "wb") as f:
                f.write(tts_response.content)

            audio_url = f"/static/audio/{audio_filename}"

            results.append(EpisodeResponse(
                title=f"Episode {i + 1}",
                description=snippet[:200] + "...",
                audio_url=audio_url
            ))

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
