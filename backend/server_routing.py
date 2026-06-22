from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from application_models import SearchSubmission, SearchResponse, DebugResponse
from consistent_hashing import get_assigned_node
from redis_manager import get_cached_suggestions, set_cached_suggestions, push_search_to_queue
from database_manager import get_top_suggestions
from trending_calculator import calculate_trending_suggestions

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/suggest")
def suggest(q: str = ""):
    if not q:
        return []
    
    node_index = get_assigned_node(q)
    cached = get_cached_suggestions(node_index, q)
    
    if cached is not None:
        return cached
        
    db_results = get_top_suggestions(q, limit=50)
    trending_results = calculate_trending_suggestions(db_results)
    top_10 = trending_results[:10]
    
    set_cached_suggestions(node_index, q, top_10)
    return top_10

@app.post("/search", response_model=SearchResponse)
def search(submission: SearchSubmission):
    push_search_to_queue(submission.query)
    return SearchResponse(message="Searched")

@app.get("/trending")
def trending():
    from trending_calculator import TRENDING_NODE
    recent_keys = TRENDING_NODE.zrevrange("trending_queries", 0, 9)
    return [{"query": key.decode('utf-8')} for key in recent_keys]

@app.get("/cache/debug", response_model=DebugResponse)
def cache_debug(prefix: str):
    node_index = get_assigned_node(prefix)
    cached = get_cached_suggestions(node_index, prefix)
    is_hit = cached is not None
    return DebugResponse(node=f"Redis DB {node_index}", is_hit=is_hit)
