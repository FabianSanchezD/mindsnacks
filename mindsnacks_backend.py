from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
import openai
import requests
import os
import uuid
from dotenv import load_dotenv
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Configure static file serving
os.makedirs("static/audio", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Load API keys from environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Check if API keys are available
if not openai.api_key:
    logger.error("OPENAI_API_KEY not found in environment variables")
if not ELEVENLABS_API_KEY:
    logger.error("ELEVENLABS_API_KEY not found in environment variables")

# Define request and response models
class EpisodeRequest(BaseModel):
    topics: List[str]
    num_episodes: int = 6

class EpisodeResponse(BaseModel):
    title: str
    description: str
    audio_url: str

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
            if len(chunk.strip()) > 100:  # Substantial content
                episodes.append({
                    "title": f"Episode {current_episode}",
                    "content": chunk.strip()
                })
                current_episode += 1
    
    logger.info(f"Successfully parsed {len(episodes)} episodes")
    for i, ep in enumerate(episodes):
        logger.debug(f"Episode {i+1} - Title: {ep['title']}, Content length: {len(ep['content'])}")
    
    return episodes

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
                 f"4. NEVER put anything after the end of the script. The TTS could read it and it is not good."
                 f"Format each episode with clear separation between episodes and make sure the script part is extensive enough to be read in about 7 minutes.")
        
        # Call OpenAI API using the new client
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",  # Updated model name
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
        
        # Process each episode
        for i, episode in enumerate(episodes[:req.num_episodes]):
            # Extract episode title and content
            title = episode["title"]
            content = episode["content"]
            
            # Create description (first few sentences or characters)
            description = content[:300] + "..." if len(content) > 300 else content
            
            try:
                # Prepare script for TTS - focus on the actual content that needs to be narrated
                # Extract a script portion from the content - look for sections likely to be the script
                script_text = content
                
                # Look for script markers like "Script:" or "---" dividers
                script_markers = [
                    "script:", "script", "content:", "transcript:", 
                    "narration:", "narration script:", "episode script:"
                ]
                
                for marker in script_markers:
                    if marker in content.lower():
                        # Extract everything after the marker
                        parts = re.split(f"(?i){re.escape(marker)}", content, 1)
                        if len(parts) > 1:
                            script_text = parts[1].strip()
                            break
                
                # If the content is very long, focus on the most substantive part
                # This helps avoid TTS limits and focuses on the actual narrative
                if len(script_text) > 4000:
                    logger.info(f"Script too long ({len(script_text)} chars), truncating to 4000 chars")
                    script_text = script_text[:4000]
                
                # Make sure we have content to narrate
                if len(script_text) < 50:
                    logger.warning(f"Script for episode {i+1} is too short, using full content")
                    script_text = content[:4000]  # Use the full content but limited to 4000 chars
                
                logger.info(f"Sending {len(script_text)} chars to ElevenLabs for episode {i+1}")
                
                # Call ElevenLabs API for text-to-speech
                tts_url = "https://api.elevenlabs.io/v1/text-to-speech/EXAVITQu4vr4xnSDxMaL"  # A specific voice ID
                
                tts_response = requests.post(
                    tts_url,
                    headers={
                        "xi-api-key": ELEVENLABS_API_KEY,
                        "Content-Type": "application/json"
                    },
                    json={
                        "text": script_text,
                        "model_id": "eleven_monolingual_v1",
                        "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
                    }
                )
                
                # Check response status and content
                if tts_response.status_code != 200:
                    logger.error(f"ElevenLabs API error: {tts_response.status_code} - {tts_response.text}")
                    raise HTTPException(
                        status_code=500, 
                        detail=f"TTS generation failed with status {tts_response.status_code}: {tts_response.text}"
                    )
                
                # Save audio file
                audio_filename = f"mindsnacks_episode_{uuid.uuid4().hex[:8]}.mp3"
                audio_path = f"static/audio/{audio_filename}"
                
                with open(audio_path, "wb") as f:
                    f.write(tts_response.content)
                
                # Construct audio URL
                audio_url = f"/static/audio/{audio_filename}"
                
                # Add to results
                results.append(
                    EpisodeResponse(
                        title=title,
                        description=description,
                        audio_url=audio_url
                    )
                )
                
                logger.info(f"Successfully generated episode {i+1}: {title}")
                
            except Exception as e:
                logger.error(f"Error processing episode {i+1}: {str(e)}")
                # Continue with other episodes instead of failing completely
        
        if not results:
            raise HTTPException(status_code=500, detail="Failed to generate any episodes")
            
        return results
        
    except Exception as e:
        logger.error(f"Error in generate_episodes: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Root endpoint for API health check
@app.get("/")
async def root():
    return {"status": "ok", "message": "MindSnacks API is running"}