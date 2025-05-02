import streamlit as st
from PIL import Image
import requests

st.set_page_config(page_title="MindSnacks", page_icon="🧠")

# Load and display the logo
logo = Image.open("img\mindsnacks_logov2_nospace.png")
st.image(logo, width=120)

st.title("🧠 MindSnacks")
st.subheader("Bite-sized learning for hungry minds")

with st.form("topic_form"):
    topics_input = st.text_input("Enter topics separated by commas", "History of AI, Why sea levels are rising")
    num_episodes = st.slider("Number of episodes", 1, 10, 6)
    submitted = st.form_submit_button("Generate Learning Playlist")

if submitted:
    topics = [topic.strip() for topic in topics_input.split(",") if topic.strip()]
    with st.spinner("Generating your personalized audio snippets..."):
        try:
            res = requests.post(
                "http://localhost:8000/generate",
                json={"topics": topics, "num_episodes": num_episodes},
                headers={"Content-Type": "application/json"}
            )
            res.raise_for_status()
            episodes = res.json()

            st.success("Here is your learning playlist:")
            for episode in episodes:
                st.markdown(f"### {episode['title']}")
                st.markdown(f"*{episode['description']}*")
                st.audio(f"http://localhost:8000{episode['audio_url']}", format="audio/mp3")

        except Exception as e:
            st.error(f"Error: {e}")
