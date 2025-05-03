from dotenv import load_dotenv
import requests
import json
from datetime import datetime, timedelta
import random
import os
from typing import List, Dict
import logging

load_dotenv()

logger = logging.getLogger(__name__)

class RecommendationEngine:
    """Recommendation engine for trending topics and personalized suggestions"""
    
    def __init__(self):
        self.cache_file = "topic_cache.json"
        self.cache_expiry = 6  # hours - reduced from 24 to refresh more frequently
        
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
                        # Handle case where the file exists but has invalid format (empty or wrong type)
                        logger.warning("Invalid data format in user topic history file. Resetting to empty list.")
                        self.popular_user_topics = []
            else:
                # Create an empty file if it doesn't exist
                with open(self.user_topic_history_file, 'w') as f:
                    json.dump([], f)
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
            # Normalize topic by converting to lowercase and trimming whitespace
            normalized_topic = topic.lower().strip()
            if not normalized_topic:
                continue
                
            # Check if topic already exists
            existing_topic = next((item for item in self.popular_user_topics 
                                if item["topic"].lower() == normalized_topic), None)
            
            if existing_topic:
                existing_topic["count"] += 1
                existing_topic["last_used"] = datetime.now().isoformat()
            else:
                self.popular_user_topics.append({
                    "topic": topic,  # Keep original capitalization for display
                    "count": 1,
                    "last_used": datetime.now().isoformat()
                })
        
        # Sort by popularity (count) and recency (last_used)
        self.popular_user_topics.sort(
            key=lambda x: (x["count"], datetime.fromisoformat(x["last_used"])), 
            reverse=True
        )
        
        # Keep only top 100 topics to avoid unlimited growth
        self.popular_user_topics = self.popular_user_topics[:100]
        
        # Save to file
        self.save_user_topic_history()
        logger.info(f"Tracked {len(topics)} topics, total unique topics: {len(self.popular_user_topics)}")

    def get_cached_topics(self) -> Dict[str, List[str]]:
        """Get cached topics if available and not expired"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    content = f.read().strip()
                    if content:  # Check if the file is not empty
                        cache_data = json.loads(content)
                        
                        # Check if cache is expired
                        cache_time = datetime.fromisoformat(cache_data.get("timestamp", "2000-01-01T00:00:00"))
                        if datetime.now() - cache_time < timedelta(hours=self.cache_expiry):
                            logger.info("Using cached recommendations")
                            return cache_data.get("topics", self.default_topics)
                        else:
                            logger.info("Cache expired, generating new recommendations")
                    else:
                        # Create a new cache with default topics if file is empty
                        logger.info("Empty cache file, generating new recommendations")
                        self.save_to_cache(self.default_topics)
                        return self.default_topics
            except json.JSONDecodeError:
                logger.error("Invalid JSON in cache file, recreating")
                self.save_to_cache(self.default_topics)
                return self.default_topics
            except Exception as e:
                logger.error(f"Error reading cache: {e}")
                return self.default_topics
        else:
            # Create cache file if it doesn't exist
            logger.info("No cache file exists, creating new recommendations")
            self.save_to_cache(self.default_topics)
            return self.default_topics
        
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
            logger.info("Saved recommendations to cache")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def extract_keywords_from_title(self, title: str) -> List[str]:
        """Extract meaningful keywords from a news title"""
        # Remove common words and punctuation that shouldn't be topics
        stop_words = ["a", "an", "the", "in", "on", "at", "to", "for", "with", "by", 
                       "from", "of", "and", "or", "but", "is", "are", "was", "were",
                       "be", "been", "being", "have", "has", "had", "do", "does", "did",
                       "will", "would", "shall", "should", "may", "might", "must", "can",
                       "could", "says", "said", "according", "reported"]
        
        # Clean and normalize the title
        cleaned_title = ''.join(c.lower() if c.isalnum() else ' ' for c in title)
        words = cleaned_title.split()
        
        # Extract words that are not stop words and are meaningful (longer than 3 chars)
        keywords = [word for word in words if word not in stop_words and len(word) > 3]
        
        return keywords

    def fetch_trending_news_topics(self) -> Dict[str, List[str]]:
        """Fetch trending topics from news API and organize by category"""
        try:
            news_api_key = os.getenv("NEWS_API_KEY")
            if not news_api_key:
                logger.warning("NEWS_API_KEY not found in environment variables")
                return {}
                
            # Categories to fetch from News API
            categories = ["business", "entertainment", "health", "science", "sports", "technology"]
            all_topics = {}
            
            for category in categories:
                try:
                    url = f"https://newsapi.org/v2/top-headlines?category={category}&language=en&pageSize=10&apiKey={news_api_key}"
                    response = requests.get(url, timeout=5)
                    
                    if response.status_code == 200:
                        data = response.json()
                        articles = data.get("articles", [])
                        
                        if not articles:
                            logger.warning(f"No articles found for category: {category}")
                            continue
                        
                        # Extract topics from titles and descriptions
                        category_topics = set()
                        for article in articles:
                            title = article.get("title", "")
                            if not title or title == "[Removed]":
                                continue
                                
                            # Extract keywords from title
                            keywords = self.extract_keywords_from_title(title)
                            
                            # Add relevant keywords as topics
                            for keyword in keywords:
                                if len(keyword) > 3:  # Only add meaningful keywords
                                    # Capitalize first letter of each word for better presentation
                                    formatted_topic = ' '.join(word.capitalize() for word in keyword.split())
                                    category_topics.add(formatted_topic)
                        
                        # Store unique topics for this category
                        if category_topics:
                            all_topics[category] = list(category_topics)[:5]  # Limit to 5 topics per category
                    else:
                        logger.error(f"News API error for {category}: {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"Error fetching {category} news: {e}")
            
            if all_topics:
                logger.info(f"Successfully fetched news topics from {len(all_topics)} categories")
                return all_topics
            else:
                logger.warning("Failed to fetch any news topics")
                return {}
                
        except Exception as e:
            logger.error(f"Error in fetch_trending_news_topics: {e}")
            return {}

    def get_popular_user_topics(self, count: int = 5) -> List[str]:
        """Get most popular topics from user history"""
        return [item["topic"] for item in self.popular_user_topics[:count] if isinstance(item, dict) and "topic" in item]

    def get_recently_used_topics(self, count: int = 5) -> List[str]:
        """Get recently used topics from user history"""
        # Sort a copy of the list by recency
        sorted_by_recency = sorted(
            self.popular_user_topics,
            key=lambda x: datetime.fromisoformat(x["last_used"]) if isinstance(x, dict) and "last_used" in x else datetime.min,
            reverse=True
        )
        return [item["topic"] for item in sorted_by_recency[:count] if isinstance(item, dict) and "topic" in item]

    def get_recommendations(self) -> Dict[str, List[str]]:
        """Get topic recommendations across different categories"""
        # First try to use cached topics if not expired
        cached_topics = self.get_cached_topics()
        if cached_topics and isinstance(cached_topics, dict) and cached_topics:
            return cached_topics
            
        # If no valid cache, generate new recommendations
        topics = {}
        
        # Add news API topics if available
        news_topics = self.fetch_trending_news_topics()
        if news_topics:
            topics.update(news_topics)
        
        # Add popular user topics if available (most selected)
        user_topics = self.get_popular_user_topics(count=5)
        if user_topics:
            topics["popular"] = user_topics
            
        # Add recently used topics if available
        recent_topics = self.get_recently_used_topics(count=5)
        if recent_topics:
            topics["recent"] = recent_topics[:5]  # Limit to 5 topics
        
        # Include default topics as a fallback for categories that didn't work
        if not news_topics:
            # If news API failed, use our default topics
            for category, category_topics in self.default_topics.items():
                if category not in topics:  # Don't overwrite existing categories
                    # Randomly select 3-5 topics from each category
                    random_count = min(random.randint(3, 5), len(category_topics))
                    topics[category] = random.sample(category_topics, random_count)
        
        # Cache the results
        if topics:
            self.save_to_cache(topics)
        else:
            # If we somehow got no topics at all, use defaults
            topics = self.default_topics
            self.save_to_cache(topics)
        
        return topics

# Initialize the recommendation engine
recommendation_engine = RecommendationEngine()

def get_recommendations(count_per_category: int = 3) -> Dict[str, List[str]]:
    """Get recommendations for the UI"""
    try:
        recommendations = recommendation_engine.get_recommendations()
        
        # Limit the number of topics per category
        for category in recommendations:
            if isinstance(recommendations[category], list):
                recommendations[category] = recommendations[category][:count_per_category]
        
        # Make sure we have at least one category
        if not recommendations:
            return {"featured": ["Quantum physics", "History of aviation", "Marine biology"]}
            
        return recommendations
    except Exception as e:
        logging.error(f"Error getting recommendations: {e}")
        # Return default recommendations if something goes wrong
        return {"featured": ["Quantum physics", "History of aviation", "Marine biology"]}

def track_topics(topics: List[str]):
    """Track topics that users select"""
    try:
        recommendation_engine.track_user_topics(topics)
    except Exception as e:
        logging.error(f"Error tracking topics: {e}")