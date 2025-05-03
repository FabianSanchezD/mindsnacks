import requests
import json
from datetime import datetime, timedelta
import random
import os
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class RecommendationEngine:
    """Recommendation engine for trending topics and personalized suggestions"""
    
    def __init__(self):
        self.cache_file = "topic_cache.json"
        self.cache_expiry = 24  # hours
        
        # Initialize with default topics in case external APIs fail
        self.default_topics = {
            "science": [
                "Quantum computing breakthroughs", 
                "CRISPR gene editing", 
                "Fusion energy progress",
                "Neuroscience of learning",
                "Climate science updates"
            ],
            "culture": [
                "Contemporary art movements",
                "Global music traditions",
                "Digital culture phenomena",
                "Cultural heritage preservation",
                "Language evolution"
            ],
            "geopolitics": [
                "International relations",
                "Economic policies",
                "Sustainability initiatives",
                "Global governance",
                "Technology regulation"
            ],
            "technology": [
                "Artificial intelligence ethics",
                "Sustainable technology",
                "Privacy and security",
                "Digital transformation",
                "Future of work"
            ]
        }
        
        # Initialize popular topics tracker
        self.popular_user_topics = []
        self.user_topic_history_file = "user_topic_history.json"
        self.load_user_topic_history()

    def load_user_topic_history(self):
        """Load tracked user topic history from file"""
        try:
            if os.path.exists(self.user_topic_history_file):
                with open(self.user_topic_history_file, 'r') as f:
                    data = json.load(f)
                    # Ensure data is a list of dictionaries
                    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
                        self.popular_user_topics = data
                    else:
                        logger.warning("Invalid data format in user topic history file. Resetting to empty list.")
                        self.popular_user_topics = []
        except Exception as e:
            logger.error(f"Error loading user topic history: {e}")
            self.popular_user_topics = []

    def save_user_topic_history(self):
        """Save tracked user topic history to file"""
        try:
            with open(self.user_topic_history_file, 'w') as f:
                json.dump(self.popular_user_topics, f)
        except Exception as e:
            logger.error(f"Error saving user topic history: {e}")

    def track_user_topics(self, topics: List[str]):
        """Track user-selected topics to build popularity data"""
        for topic in topics:
            # Check if topic already exists
            existing_topic = next((item for item in self.popular_user_topics 
                                if item["topic"].lower() == topic.lower()), None)
            
            if existing_topic:
                existing_topic["count"] += 1
                existing_topic["last_used"] = datetime.now().isoformat()
            else:
                self.popular_user_topics.append({
                    "topic": topic,
                    "count": 1,
                    "last_used": datetime.now().isoformat()
                })
        
        # Sort by popularity
        self.popular_user_topics.sort(key=lambda x: x["count"], reverse=True)
        
        # Keep only top 100 topics to avoid unlimited growth
        self.popular_user_topics = self.popular_user_topics[:100]
        
        # Save to file
        self.save_user_topic_history()

    def get_cached_topics(self) -> Dict[str, List[str]]:
        """Get cached topics if available and not expired"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                # Check if cache is expired
                cache_time = datetime.fromisoformat(cache_data.get("timestamp", "2000-01-01T00:00:00"))
                if datetime.now() - cache_time < timedelta(hours=self.cache_expiry):
                    return cache_data.get("topics", self.default_topics)
            except Exception as e:
                logger.error(f"Error reading cache: {e}")
        
        return None

    def save_to_cache(self, topics: Dict[str, List[str]]):
        """Save topics to cache with timestamp"""
        try:
            cache_data = {
                "timestamp": datetime.now().isoformat(),
                "topics": topics
            }
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f)
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def fetch_trending_news_topics(self) -> List[str]:
        """Fetch trending topics from news API"""
        try:
            # If you have a NewsAPI.org API key
            # Replace with your actual API key
            news_api_key = os.getenv("NEWS_API_KEY", "")
            if not news_api_key:
                return []
                
            url = f"https://newsapi.org/v2/top-headlines?language=en&apiKey={news_api_key}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                # Extract keywords from titles
                titles = [article["title"] for article in data.get("articles", []) if article.get("title")]
                
                # Simple keyword extraction (in production, use NLP for better results)
                topics = []
                for title in titles:
                    # Split title into words and keep words with 4+ characters
                    words = [word for word in title.split() if len(word) > 4]
                    if words:
                        topics.append(words[0])
                
                return list(set(topics))[:5]  # Return up to 5 unique topics
            
            return []
        except Exception as e:
            logger.error(f"Error fetching news topics: {e}")
            return []

    def get_popular_user_topics(self, count: int = 5) -> List[str]:
        """Get most popular topics from user history"""
        return [item["topic"] for item in self.popular_user_topics[:count] if isinstance(item, dict) and "topic" in item]

    def get_recommendations(self, count: int = 5) -> Dict[str, List[str]]:
        """Get topic recommendations across different categories"""
        # First try to use cached topics
        cached_topics = self.get_cached_topics()
        if cached_topics:
            return cached_topics
            
        # Otherwise generate new recommendations
        topics = {}
        
        # Add trending news topics if available
        news_topics = self.fetch_trending_news_topics()
        if news_topics:
            topics["trending_news"] = news_topics
        
        # Add popular user topics if available
        user_topics = self.get_popular_user_topics()
        if user_topics:
            topics["popular"] = user_topics
        
        # Add topics from predefined categories
        for category, category_topics in self.default_topics.items():
            # Randomly select 3-5 topics from each category
            random_count = min(random.randint(3, 5), len(category_topics))
            topics[category] = random.sample(category_topics, random_count)
        
        # Cache the results
        self.save_to_cache(topics)
        
        return topics

# Initialize the recommendation engine
recommendation_engine = RecommendationEngine()

def get_recommendations(count_per_category: int = 3) -> Dict[str, List[str]]:
    """Get recommendations for the UI"""
    recommendations = recommendation_engine.get_recommendations()
    
    # Limit the number of topics per category
    for category in recommendations:
        recommendations[category] = recommendations[category][:count_per_category]
    
    return recommendations

def track_topics(topics: List[str]):
    """Track topics that users select"""
    recommendation_engine.track_user_topics(topics)
