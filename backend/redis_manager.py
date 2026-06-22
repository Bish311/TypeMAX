import redis
import json
import os
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

CACHE_NODES = {
    0: redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0),
    1: redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=1),
    2: redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=2)
}

QUEUE_NODE = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=9)
SEARCH_QUEUE_KEY = "search_queue"

def get_cached_suggestions(node_index, prefix):
    cache = CACHE_NODES[node_index]
    result = cache.get(prefix)
    if result:
        return json.loads(result)
    return None

def set_cached_suggestions(node_index, prefix, suggestions):
    cache = CACHE_NODES[node_index]
    cache.set(prefix, json.dumps(suggestions), ex=300)

def push_search_to_queue(query):
    QUEUE_NODE.rpush(SEARCH_QUEUE_KEY, query)

def pop_searches_from_queue(batch_size=50):
    pipe = QUEUE_NODE.pipeline()
    pipe.lrange(SEARCH_QUEUE_KEY, 0, batch_size - 1)
    pipe.ltrim(SEARCH_QUEUE_KEY, batch_size, -1)
    results = pipe.execute()
    
    searches = results[0]
    return [q.decode('utf-8') for q in searches]
