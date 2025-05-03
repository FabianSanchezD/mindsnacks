# Description

Ever wondered how to turn dead time into brain time?

## Introducing MindSnacks, bite-sized learning for hungry minds! 

Whether you are going for a run/walk, washing your clothes, cooking your favorite meal; you can now use that extra time to do your task and learn new things! 

Just ask MindSnacks to generate quick learning (5-minute) episodes about topics you are interested in: like the history of Costa Rica, the start of computers, Sam Altman’s story, you name it. 

Not sure what to learn? Just type your interest and get a personalized audio playlist ready to go. Learning has never been this effortless.

### MindSnacks makes learning as easy as pressing play.

# Technologies
- OpenAI's API to generate quick text learning episodes about the input
- 11Labs's API for TTS conversion
- News API for finding trending topics for recommendations
- Python, Streamlit (frontend), FastAPI (backend) HTML/CSS (just a bit)

# Setup
## 2 ways to try this app:
## a. Using the already deployed version (recommended)
1. Click this link: https://mindsnacks.streamlit.app/

Posible limitations: I run out of API Credits, mostly 11Labs (only 6k left). 

## b. Cloning this repo
1. Clone this repo
2. Create  `.env` with your API Keys for OpenAI, 11Labs and News API like this:

```
OPENAI_API_KEY=your_openai_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
NEWS_API_KEY=your_newsapi_key
```
Note: 11Labs and NewsAPI provide free trials that could be used to try this out.

3. IMPORTANT: The files on GitHub are made so that the app is deployed, so we need to change everywhere `https://mindsnacks.onrender.com` this appears, to `http://localhost:8000/`. (This is ONLY on the `streamlit_ui.py` file)

3. Install all dependencies with  `pip install -r requirements.txt`
4. Run backend with: `python run main.py`
5. Run frontend with:  ``


# Features & Usage

- Generate bite-sized audio learning episodes on any topic
- Dynamic topic recommendations from multiple sources: Current news headlines via News API integration, popular topics based on user selection history, recently selected topics for quick access, etc...
- Search functionality for your learning history
- Audio player with download capability for offline listening
- "Fill my curiosity" button for topic discovery

### This project was created for Global MIT AI Hackathon 2025 by Fabian Sanchez.
