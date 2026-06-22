import redis
import os
import time
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

TRENDING_NODE = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=8)

def record_recent_search(query):
    current_time = int(time.time())
    key = f"recent_search:{query}"
    TRENDING_NODE.zadd("trending_queries", {query: current_time})
    TRENDING_NODE.incr(key)
    TRENDING_NODE.expire(key, 7200)

def get_recent_count(query):
    key = f"recent_search:{query}"
    count = TRENDING_NODE.get(key)
    if count:
        return int(count)
    return 0

def calculate_trending_suggestions(db_results, recency_weight=50):
    scored_results = []
    for item in db_results:
        query = item["query"]
        all_time_count = item["count"]
        recent_count = get_recent_count(query)
        
        score = all_time_count + (recent_count * recency_weight)
        scored_results.append({
            "query": query,
            "count": all_time_count,
            "score": score
        })
        
    scored_results.sort(key=lambda x: x["score"], reverse=True)
    
    final_results = []
    for item in scored_results:
        final_results.append({"query": item["query"], "count": item["count"]})
        
    return final_results
