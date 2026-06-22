import time
from redis_manager import pop_searches_from_queue, CACHE_NODES
from database_manager import upsert_queries_batch
from trending_calculator import record_recent_search

def invalidate_cache(prefix_to_invalidate):
    from consistent_hashing import get_assigned_node
    node_index = get_assigned_node(prefix_to_invalidate)
    cache = CACHE_NODES[node_index]
    cache.delete(prefix_to_invalidate)

def process_search_batch():
    searches = pop_searches_from_queue(batch_size=50)
    if not searches:
        return
        
    aggregated_counts = {}
    prefixes_to_invalidate = set()
    
    for query in searches:
        if query in aggregated_counts:
            aggregated_counts[query] += 1
        else:
            aggregated_counts[query] = 1
            
        record_recent_search(query)
        
        for i in range(1, len(query) + 1):
            prefixes_to_invalidate.add(query[:i])
            
    upsert_queries_batch(aggregated_counts)
    
    for prefix in prefixes_to_invalidate:
        invalidate_cache(prefix)

def start_background_processor():
    while True:
        process_search_batch()
        time.sleep(5)

if __name__ == "__main__":
    start_background_processor()
