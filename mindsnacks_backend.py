from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Optional
import openai
import requests
import os
import uuid
from dotenv import load_dotenv
import re
import logging
import time
import json
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Configure static file serving
os.makedirs("static/audio", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

openai.api_key = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

if not openai.api_key:
    logger.error("OPENAI_API_KEY not found in environment variables")
if not ELEVENLABS_API_KEY:
    logger.error("ELEVENLABS_API_KEY not found in environment variables")

# Rate limiting configuration
RATE_LIMIT_FILE = "elevenlabs_rate_limit.json"
ELEVENLABS_CHAR_LIMIT = 30000  # 11Labs limit of 30,000 chars per 5 minutes
ELEVENLABS_WINDOW_SECONDS = 300  # 5 minutes in seconds

class ElevenLabsRateLimiter:
    """Rate limiter for ElevenLabs API to prevent quota exceeded errors"""
    
    def __init__(self):
        self.usage_file = RATE_LIMIT_FILE
        self.char_limit = ELEVENLABS_CHAR_LIMIT
        self.window_seconds = ELEVENLABS_WINDOW_SECONDS
        self.usage_history = self._load_usage_history()
        
    def _load_usage_history(self) -> list:
        """Load usage history from file"""
        try:
            if os.path.exists(self.usage_file):
                with open(self.usage_file, 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Error loading rate limit history: {e}")
            return []
            
    def _save_usage_history(self):
        """Save usage history to file"""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(self.usage_history, f)
        except Exception as e:
            logger.error(f"Error saving rate limit history: {e}")
            
    def _clean_old_entries(self):
        """Remove entries outside the current window"""
        current_time = datetime.now()
        window_start = current_time - timedelta(seconds=self.window_seconds)
        
        # Convert to timestamp for comparison
        window_start_ts = window_start.timestamp()
        
        # Filter out old entries
        self.usage_history = [
            entry for entry in self.usage_history 
            if entry["timestamp"] >= window_start_ts
        ]
    
    def check_quota(self, char_count: int) -> Dict:
        """Check if request can be processed within quota limits
        
        Returns:
            Dict with {"allowed": bool, "remaining": int, "wait_time": int}
        """
        self._clean_old_entries()
        
        # Calculate total used in current window
        total_used = sum(entry["chars"] for entry in self.usage_history)
        remaining = self.char_limit - total_used
        
        if char_count <= remaining:
            return {"allowed": True, "remaining": remaining, "wait_time": 0}
        
        # Calculate wait time if quota exceeded
        if not self.usage_history:
            # If no history but still over limit, the request is just too large
            return {"allowed": False, "remaining": remaining, "wait_time": self.window_seconds}
            
        # Find oldest entry to estimate wait time
        oldest_entry = min(self.usage_history, key=lambda x: x["timestamp"])
        oldest_time = datetime.fromtimestamp(oldest_entry["timestamp"])
        time_until_free = (oldest_time + timedelta(seconds=self.window_seconds)) - datetime.now()
        
        wait_seconds = max(0, time_until_free.total_seconds())
        
        return {
            "allowed": False, 
            "remaining": remaining, 
            "wait_time": int(wait_seconds)
        }
    
    def record_usage(self, char_count: int):
        """Record API usage"""
        self.usage_history.append({
            "timestamp": datetime.now().timestamp(),
            "chars": char_count
        })
        self._save_usage_history()

# Initialize rate limiter
rate_limiter = ElevenLabsRateLimiter()

class EpisodeRequest(BaseModel):
    topics: List[str]
    num_episodes: int = 6

class EpisodeResponse(BaseModel):
    title: str
    description: str
    audio_url: str
    transcript: Optional[str] = None  # Added for text-only mode

def parse_episodes(text):
    """Parse episodes from generated text"""
    episodes = []
    logger.info("Parsing generated text into episodes")
    logger.debug(f"Raw text: {text[:200]}...")
    
    # First, try to split by episode headers
    episode_blocks = re.split(r"(?=Episode \d+:|Title:|# Episode \d+)", text)
    
    if len(episode_blocks) > 1:
        # Process each block that starts with an episode indicator
        for block in episode_blocks:
            if not block.strip():
                continue
                
            # Extract title and content
            lines = block.strip().split('\n', 1)
            
            if len(lines) >= 2:
                title = lines[0].strip()
                content = lines[1].strip()
                
                # Make sure we have substantial content
                if len(content) > 50:  # Ensure we have more than just a title or brief description
                    episodes.append({
                        "title": title,
                        "content": content
                    })
    
    # If that doesn't work well, try another approach with regex
    if len(episodes) < 2:
        logger.info("First parsing method didn't work well, trying alternative")
        pattern = r"(Episode \d+.*?|Title:.*?)[\n\r]+(.*?)(?=\n\s*(?:Episode \d+|Title:|$))"
        matches = re.findall(pattern, text, re.DOTALL)
        
        episodes = []
        for title_part, content in matches:
            title = title_part.strip()
            content = content.strip()
            
            if title and len(content) > 50:
                episodes.append({
                    "title": title,
                    "content": content
                })
    
    # Last resort: just break it into chunks
    if len(episodes) < 2:
        logger.info("Both parsing methods failed, falling back to simple chunking")
        chunks = text.split("\n\n\n")
        current_episode = 1
        
        for chunk in chunks:
            if len(chunk.strip()) > 100:  
                episodes.append({
                    "title": f"Episode {current_episode}",
                    "content": chunk.strip()
                })
                current_episode += 1
    
    logger.info(f"Successfully parsed {len(episodes)} episodes")
    for i, ep in enumerate(episodes):
        logger.debug(f"Episode {i+1} - Title: {ep['title']}, Content length: {len(ep['content'])}")
    
    return episodes

def extract_script_from_content(content: str):
    """Extract the script portion from the episode content"""
    script_text = content
    
    # Look for script markers like "Script:" or "---" dividers
    script_markers = [
        "script:", "script", "content:", "transcript:", 
        "narration:", "narration script:", "episode script:"
    ]
    
    for marker in script_markers:
        if marker in content.lower():
            parts = re.split(f"(?i){re.escape(marker)}", content, 1)
            if len(parts) > 1:
                script_text = parts[1].strip()
                break
    
    # If the content is very long, focus on the most substantive part
    if len(script_text) > 4000:
        logger.info(f"Script too long ({len(script_text)} chars), truncating to 4000 chars")
        script_text = script_text[:4000]
    
    if len(script_text) < 50:
        logger.warning(f"Script is too short, using full content")
        script_text = content[:4000] 
    
    return script_text

def generate_speech_with_elevenlabs(text: str) -> tuple:
    """Generate speech using ElevenLabs API with rate limiting"""
    # Check quota before proceeding
    quota_check = rate_limiter.check_quota(len(text))
    
    if not quota_check["allowed"]:
        wait_time = quota_check["wait_time"]
        if wait_time < 60:  # If wait time is less than a minute, wait and retry
            logger.info(f"Rate limit reached. Waiting {wait_time} seconds before retrying.")
            time.sleep(wait_time)
            # Re-check after waiting
            quota_check = rate_limiter.check_quota(len(text))
            if not quota_check["allowed"]:
                raise Exception(f"Rate limit still exceeded after waiting. Please try again in {quota_check['wait_time']} seconds.")
        else:
            raise Exception(f"ElevenLabs API rate limit reached. Please try again in {wait_time} seconds.")
    
    # Record usage before making the request
    rate_limiter.record_usage(len(text))
    
    # Call ElevenLabs API
    tts_url = "https://api.elevenlabs.io/v1/text-to-speech/EXAVITQu4vr4xnSDxMaL"
    
    tts_response = requests.post(
        tts_url,
        headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
        }
    )
    
    if tts_response.status_code != 200:
        logger.error(f"ElevenLabs API error: {tts_response.status_code} - {tts_response.text}")
        raise Exception(f"TTS generation failed with status {tts_response.status_code}: {tts_response.text}")
    
    # Save audio file
    audio_filename = f"mindsnacks_episode_{uuid.uuid4().hex[:8]}.mp3"
    audio_path = f"static/audio/{audio_filename}"
    
    with open(audio_path, "wb") as f:
        f.write(tts_response.content)
    
    return f"/static/audio/{audio_filename}", audio_filename

@app.post("/generate", response_model=List[EpisodeResponse])
async def generate_episodes(req: EpisodeRequest):
    try:
        if not req.topics:
            raise HTTPException(status_code=400, detail="No topics provided")
        
        # Join topics for the prompt
        topics_text = ", ".join(req.topics)
        
        # Create the prompt
        logger.info(f"Generating {req.num_episodes} episodes on topics: {topics_text}")
        prompt = (f"Create {req.num_episodes} educational podcast episode scripts (~7 minutes each) "
                 f"on these topics: {topics_text}. For each episode, include:\n"
                 f"1. A title that starts with 'Episode X:' where X is the episode number\n"
                 f"2. A 3 sentence description of the episode content\n"
                 f"3. A complete narration script clearly labeled as 'SCRIPT:' that's ready to be read aloud\n\n"
                 f"4. NEVER put anything after the end of the script. The TTS could read it and it is not good.")
        
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview", 
            messages=[
                {"role": "system", "content": "You are a brilliant educational podcaster who creates clear, engaging 7-minute scripts."}, 
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        # Extract generated content
        generated_text = response.choices[0].message.content
        logger.info(f"Generated text length: {len(generated_text)}")
        
        # Parse episodes from the generated text
        episodes = parse_episodes(generated_text)
        logger.info(f"Parsed {len(episodes)} episodes")
        
        if not episodes:
            raise HTTPException(status_code=500, detail="Failed to parse episodes from generated content")
        
        results = []
        
        # Process each episode - with retries and fallbacks
        for i, episode in enumerate(episodes[:req.num_episodes]):
            try:
                title = episode["title"]
                content = episode["content"]
                
                # Extract script for TTS
                script_text = extract_script_from_content(content)
                logger.info(f"Processing episode {i+1}: {title} ({len(script_text)} chars)")
                
                # Try to generate audio, with fallback to text-only mode
                try:
                    audio_url, _ = generate_speech_with_elevenlabs(script_text)
                    # Add to results
                    results.append(
                        EpisodeResponse(
                            title=title,
                            description=content,
                            audio_url=audio_url,
                            transcript=script_text
                        )
                    )
                    logger.info(f"Successfully generated audio for episode {i+1}")
                    
                except Exception as audio_error:
                    logger.warning(f"Audio generation failed for episode {i+1}: {str(audio_error)}")
                    # Fall back to text-only mode
                    results.append(
                        EpisodeResponse(
                            title=title,
                            description=content,
                            audio_url="/static/audio/quota_exceeded.mp3",  # Placeholder or error audio
                            transcript=script_text
                        )
                    )
                    logger.info(f"Added episode {i+1} in text-only mode")
                
            except Exception as episode_error:
                logger.error(f"Error processing episode {i+1}: {str(episode_error)}")
                # Continue to next episode instead of failing completely
        
        if not results:
            raise HTTPException(status_code=500, detail="Failed to generate any episodes")
            
        return results
        
    except Exception as e:
        logger.error(f"Error in generate_episodes: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"status": "ok", "message": "MindSnacks API is running"}

# Create a placeholder audio file for quota exceeded cases
def create_placeholder_audio():
    placeholder_path = "static/audio/quota_exceeded.mp3"
    if not os.path.exists(placeholder_path):
        try:
            # Try to create a very simple audio file with minimal TTS if possible
            # This is just a one-time operation on startup
            minimal_text = "I'm sorry, but the audio generation quota has been exceeded. Please try again later or read the transcript below."
            
            # Try with ElevenLabs if we have any quota left
            try:
                quota_check = rate_limiter.check_quota(len(minimal_text))
                if quota_check["allowed"]:
                    tts_url = "https://api.elevenlabs.io/v1/text-to-speech/EXAVITQu4vr4xnSDxMaL"
                    tts_response = requests.post(
                        tts_url,
                        headers={
                            "xi-api-key": ELEVENLABS_API_KEY,
                            "Content-Type": "application/json"
                        },
                        json={
                            "text": minimal_text,
                            "model_id": "eleven_monolingual_v1",
                            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
                        }
                    )
                    
                    if tts_response.status_code == 200:
                        with open(placeholder_path, "wb") as f:
                            f.write(tts_response.content)
                        rate_limiter.record_usage(len(minimal_text))
                        logger.info("Created placeholder audio file")
                        return
            except Exception as e:
                logger.warning(f"Failed to create placeholder audio with ElevenLabs: {e}")
                
            # If that fails, use a static placeholder
            logger.warning("Using a static placeholder for quota exceeded audio")
            # In a real app, you'd include a default MP3 file in your repo
            
        except Exception as e:
            logger.error(f"Failed to create placeholder audio: {e}")

# Create placeholder audio on startup
create_placeholder_audio()