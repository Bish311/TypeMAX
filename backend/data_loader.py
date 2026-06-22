import urllib.request
from database_manager import initialize_schema, get_database_connection
import os

DATASET_URL = "https://norvig.com/ngrams/count_2w.txt"
DATASET_FILENAME = "count_2w.txt"
BATCH_INSERT_LIMIT = 5000

def download_dataset():
    if not os.path.exists(DATASET_FILENAME):
        urllib.request.urlretrieve(DATASET_URL, DATASET_FILENAME)

def ingest_dataset():
    download_dataset()
    initialize_schema()
    
    connection = get_database_connection()
    cursor = connection.cursor()
    cursor.execute("TRUNCATE TABLE search_queries")
    connection.commit()
    
    import redis_manager
    redis_manager.QUEUE_NODE.flushall()
    
    batch_records = []
    with open(DATASET_FILENAME, "r", encoding="utf-8") as dataset_file:
        for line in dataset_file:
            parts = line.strip().rsplit(maxsplit=1)
            if len(parts) == 2:
                query_text = parts[0]
                query_count = int(parts[1])
                batch_records.append((query_text, query_count))
                
                if len(batch_records) >= BATCH_INSERT_LIMIT:
                    cursor.executemany("""
                        INSERT INTO search_queries (query, count)
                        VALUES (%s, %s)
                        ON CONFLICT (query) DO NOTHING
                    """, batch_records)
                    connection.commit()
                    batch_records = []
                    
    if len(batch_records) > 0:
        cursor.executemany("""
            INSERT INTO search_queries (query, count)
            VALUES (%s, %s)
            ON CONFLICT (query) DO NOTHING
        """, batch_records)
        connection.commit()
        
    cursor.close()
    connection.close()

if __name__ == "__main__":
    ingest_dataset()
