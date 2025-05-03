import streamlit as st
from PIL import Image
import requests
import json
import os
from datetime import datetime
from urllib.parse import urljoin
import base64

# Import our recommendation engine and random for "Fill my curiosity"
from curiosity_recommendations import get_recommendations, track_topics
import random
import time


# Page configuration
st.set_page_config(
    page_title="MindSnacks",
    page_icon="🧠",
    layout="wide"
)

# Initialize session state variables
if 'history' not in st.session_state:
    st.session_state.history = []
    # Try to load history from file
    if os.path.exists("user_history.json"):
        try:
            with open("user_history.json", "r") as f:
                st.session_state.history = json.load(f)
        except:
            pass

# Initialize topics_input in session state
if 'topics_input' not in st.session_state:
    st.session_state.topics_input = ""

# Initialize num_episodes in session state
if 'num_episodes' not in st.session_state:
    st.session_state.num_episodes = 3
    
# Initialize warning state
if 'show_warning' not in st.session_state:
    st.session_state.show_warning = False
    st.session_state.warning_message = ""
    st.session_state.warning_time = 0

# Function to remove a topic from the list
def remove_topic(index):
    topics_list = [t.strip() for t in st.session_state.topics_input.split(",") if t.strip()]
    if 0 <= index < len(topics_list):
        topics_list.pop(index)
        st.session_state.topics_input = ", ".join(topics_list)
        update_episode_count()

# Function to set a warning with minimum display time
def set_warning(message):
    st.session_state.show_warning = True
    st.session_state.warning_message = message
    st.session_state.warning_time = time.time()

# Function to generate random topics for "Fill my curiosity"
def fill_my_curiosity():
    # Get all available recommendations
    all_recommendations = get_recommendations(5)  # Get more recommendations
    
    # Flatten all recommendations into a single list
    all_topics = []
    for category, topics in all_recommendations.items():
        all_topics.extend(topics)
    
    # Shuffle and select random topics (1-3)
    random.shuffle(all_topics)
    num_topics = random.randint(1, 3)
    selected_topics = all_topics[:num_topics]
    
    # Clear existing topics and add new ones
    st.session_state.topics_input = ", ".join(selected_topics)
    update_episode_count()

def save_history():
    """Save user history to file"""
    try:
        with open("user_history.json", "w") as f:
            json.dump(st.session_state.history, f)
    except Exception as e:
        st.error(f"Error saving history: {e}")

# Function to add episode to history
def add_to_history(topics, episodes):
    history_entry = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topics": topics,
        "episodes": episodes
    }
    st.session_state.history.insert(0, history_entry)  # Add to beginning
    # Keep only the most recent 50 entries
    st.session_state.history = st.session_state.history[:50]
    save_history()
    
# Function to update episode count based on topic count
def update_episode_count():
    topics_input = st.session_state.topics_input
    if topics_input:
        # Count the number of topics in the input
        if "," in topics_input:
            topic_count = len([t.strip() for t in topics_input.split(",") if t.strip()])
            # Use the topic count as default, but cap it between 1-10
            st.session_state.num_episodes = max(1, min(10, topic_count))
        elif topics_input.strip():
            # If there's just one topic without commas
            st.session_state.num_episodes = 1
    else:
        # If no topics, set to default
        st.session_state.num_episodes = 3

# Function to update topics input when a recommendation is clicked
def add_recommendation(topic):
    # Get current topic count
    current_topics = []
    if st.session_state.topics_input:
        current_topics = [t.strip() for t in st.session_state.topics_input.split(",") if t.strip()]
    
    # Check if adding would exceed the limit
    if len(current_topics) >= 10:
        # Too many topics already, show warning
        set_warning("Maximum 10 topics allowed. Please remove a topic before adding more.")
        return False
    
    # Check if the topic is already in the input to avoid duplicates
    if not current_topics or topic.lower() not in [t.lower() for t in current_topics]:
        if st.session_state.topics_input:
            # Add comma separator if there's already text
            st.session_state.topics_input += f", {topic}"
        else:
            # First topic being added
            st.session_state.topics_input = topic
        
        # Update the number of episodes based on the new topic count
        update_episode_count()
        return True
    return False

# Function to create a download link for audio files
def get_download_link(audio_url, filename):
    try:
        # Construct full URL to fetch audio file
        if audio_url.startswith('http'):
            full_url = audio_url
        else:
            full_url = f"https://mindsnacks.onrender.com{audio_url}"
        
        # Get file content
        response = requests.get(full_url)
        response.raise_for_status()  # Raise exception for bad status codes
        
        # Encode file content to base64
        b64 = base64.b64encode(response.content).decode()
        
        # Create download link
        href = f'<a href="data:audio/mp3;base64,{b64}" download="{filename}">📥 Download MP3</a>'
        return href
    except Exception as e:
        return f"<span style='color:red'>Download error: {str(e)}</span>"

# Header and logo
col1, col2 = st.columns([1, 5])
with col1:
    try:
        logo = Image.open("mindsnacks_logov2_nospace.png")
        st.image(logo, width=120)
    except Exception as e:
        st.error(f"Could not load logo: {e}")
with col2:
    st.title("🧠 MindSnacks")
    st.subheader("Bite-sized learning for hungry minds")

# Create tabs for different views
tab1, tab2 = st.tabs(["Create", "History"])

with tab1:
    # Main column layout
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("### What do you want to learn about today?")
        
        # Display persistent warning if needed
        if st.session_state.show_warning:
            # Check if the warning has been displayed for at least 2 seconds
            if time.time() - st.session_state.warning_time < 2:
                st.warning(st.session_state.warning_message, icon="⚠️")
            else:
                # Reset warning after 2 seconds
                st.session_state.show_warning = False
        
        #Personally, adding a box feature for each topic would be good.
        
        # Now add hidden text area for storing the actual comma-separated values
        topics_input = st.text_area(
            "Enter topics or a question",
            value=st.session_state.topics_input,
            placeholder="Example: 'Tell me about quantum computing, AI ethics, and sustainable architecture' or 'I want to understand how black holes work'",
            height=100,
            key="topics_text_area",
            label_visibility="collapsed" if st.session_state.topics_input else "visible"
        )
        
        # Update session state when user changes the text area
        if st.session_state.topics_input != topics_input:
            st.session_state.topics_input = topics_input
            # Update episode count if the text has changed
            update_episode_count()
        
        # Options in an expander for simplicity
        with st.expander("Options"):
            # Calculate default number of episodes based on topics
            default_episodes = 3  # Default value
            if topics_input:
                # Count the number of topics in the input
                if "," in topics_input:
                    topic_count = len([t.strip() for t in topics_input.split(",") if t.strip()])
                    # Use the topic count as default, but cap it between 1-10
                    default_episodes = max(1, min(10, topic_count))
                elif topics_input.strip():
                    # If there's just one topic without commas
                    default_episodes = 1
            
            # Initialize slider session state if it doesn't exist
            if 'num_episodes' not in st.session_state:
                st.session_state.num_episodes = default_episodes
            
            # Update session state if default has changed
            if default_episodes != st.session_state.num_episodes:
                st.session_state.num_episodes = default_episodes
            
            num_episodes = st.slider("Number of episodes", 1, 10, st.session_state.num_episodes, key="episode_slider")
        
        # Create two columns for the buttons
        button_col1, button_col2 = st.columns([3, 2])
        
        with button_col1:
            # Submit button
            if st.button("Create My Learning Playlist", type="primary", use_container_width=True):
                # Process the input to extract topics
                if "," in topics_input:
                    # Handle comma-separated list
                    topics = [topic.strip() for topic in topics_input.split(",") if topic.strip()]
                else:
                    # For natural language, we'll treat the whole input as one topic
                    # In a production app, you might use NLP to extract keywords
                    topics = [topics_input.strip()]
                
                if not topics:
                    st.error("Please enter at least one topic")
                else:
                    with st.spinner("Generating your personalized audio snippets..."):
                        try:
                            # Track user topics for recommendations
                            track_topics(topics)
                            
                            # Call the API to generate episodes
                            api_url = "http://localhost:8000/generate"  # Use local dev server if available
                            try:
                                res = requests.post(
                                    api_url,
                                    json={"topics": topics, "num_episodes": num_episodes},
                                    headers={"Content-Type": "application/json"},
                                    timeout=2  # Short timeout to check if local server is available
                                )
                            except requests.exceptions.RequestException:
                                # Fall back to production server if local server not available
                                api_url = "https://mindsnacks.onrender.com/generate"
                                res = requests.post(
                                    api_url,
                                    json={"topics": topics, "num_episodes": num_episodes},
                                    headers={"Content-Type": "application/json"}
                                )
                                
                            res.raise_for_status()
                            episodes = res.json()
                            
                            # Add to history
                            add_to_history(topics, episodes)
                            
                            # Display results
                            st.success(f"Created {len(episodes)} learning episodes!")
                            
                            for i, episode in enumerate(episodes):
                                with st.expander(f"{episode['title']}", expanded=(i == 0)):
                                    # Clean description (remove markdown characters)
                                    clean_description = episode['description'].replace('*', '').replace('#', '')
                                    st.markdown(f"*{clean_description}*")
                                    
                                    # Audio source URL - handle both relative and absolute URLs
                                    audio_url = episode['audio_url']
                                    if not audio_url.startswith('http'):
                                        audio_url = f"https://mindsnacks.onrender.com{audio_url}"
                                    
                                    # Display audio player
                                    st.audio(audio_url, format="audio/mp3")
                                    
                                    # Add download button
                                    filename = f"{episode['title'].replace(':', '-').replace(' ', '_')}.mp3"
                                    download_link = get_download_link(episode['audio_url'], filename)
                                    st.markdown(download_link, unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"Error: {e}")
        
        with button_col2:
            # Fill my curiosity button
            if st.button("🎲 Fill my curiosity!", use_container_width=True):
                fill_my_curiosity()
                st.rerun()
    
    # Recommendations sidebar
    with col2:
        st.markdown("### 💡 Curious about...")
        
        # Get topic recommendations
        recommendations = get_recommendations()
        
        # Check if recommendations are empty or not properly formatted
        if not recommendations or not isinstance(recommendations, dict) or len(recommendations) == 0:
            st.warning("Recommendation system is currently not available. Please try again later.")
        else:
            for category, topics in recommendations.items():
                if topics:  # Only show categories with topics
                    st.markdown(f"**{category.replace('_', ' ').title()}**")
                    for topic in topics:
                        if st.button(f"➕ {topic}", key=f"recommendation_{topic}"):
                            added = add_recommendation(topic)
                            if added:
                                st.rerun()

# History tab
with tab2:
    st.markdown("### Your Learning History")
    
    if not st.session_state.history:
        st.info("Your learning history will appear here")
    else:
        # Add search box for history
        search_term = st.text_input("Search your history", "")
        
        # Filter history based on search term
        filtered_history = st.session_state.history
        if search_term:
            filtered_history = [
                entry for entry in st.session_state.history
                if any(search_term.lower() in topic.lower() for topic in entry["topics"])
                or any(search_term.lower() in ep["title"].lower() for ep in entry["episodes"])
            ]
        
        # Show message if no results found
        if search_term and not filtered_history:
            st.warning("No results found. Try a different search term.")
        
        # Display history entries
        for entry in filtered_history:
            with st.expander(f"{entry['date']} - Topics: {', '.join(entry['topics'])}"):
                for episode in entry["episodes"]:
                    st.markdown(f"**{episode['title']}**")
                    
                    # Clean description (remove markdown characters)
                    clean_description = episode['description'].replace('*', '').replace('#', '')
                    st.markdown(f"*{clean_description}*")
                    
                    # Audio source URL - handle both relative and absolute URLs
                    audio_url = episode['audio_url']
                    if not audio_url.startswith('http'):
                        audio_url = f"https://mindsnacks.onrender.com{audio_url}"
                    
                    # Display audio player
                    st.audio(audio_url, format="audio/mp3")
                    
                    # Add download button
                    filename = f"{episode['title'].replace(':', '-').replace(' ', '_')}.mp3"
                    download_link = get_download_link(episode['audio_url'], filename)
                    st.markdown(download_link, unsafe_allow_html=True)
                
                # Add a re-generate button
                if st.button("Regenerate this playlist", key=f"regen_{entry['date']}"):
                    st.session_state.topics_input = ", ".join(entry["topics"])
                    st.rerun()

# Add CSS for better styling
st.markdown("""
<style>
    .stButton button {
        border-radius: 20px;
    }
    /* Hide the default remove buttons in the topic list */
    .topic-list .stButton button {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border-width: 0;
    }
    /* Style for custom remove button hover */
    button.remove-topic:hover {
        background-color: #d32f2f !important;
    }
    .main .block-container {
        padding-top: 2rem;
    }
    .stTabs [data-baseweb="tab-list"] button {
        font-size: 1.2rem;
    }
    /* Hide the default text area when there are topics */
    .hide-label label {
        display: none;
    }
    /* Download button styling */
    a[download] {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        margin-top: 0.5rem;
        text-decoration: none;
        background-color: #f0f2f6;
        color: #262730;
        border-radius: 0.5rem;
        font-size: 0.875rem;
        transition: background-color 0.2s;
    }
    a[download]:hover {
        background-color: #e0e2e6;
    }
</style>
""", unsafe_allow_html=True)