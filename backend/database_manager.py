import psycopg2
from psycopg2 import pool
import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "typemax")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")

MIN_CONNECTIONS = 2
MAX_CONNECTIONS = 10

connection_pool = pool.SimpleConnectionPool(
    MIN_CONNECTIONS,
    MAX_CONNECTIONS,
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

def get_database_connection():
    return connection_pool.getconn()

def return_database_connection(connection):
    connection_pool.putconn(connection)

def initialize_schema():
    connection = get_database_connection()
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_queries (
            query TEXT PRIMARY KEY,
            count BIGINT DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_query_prefix
        ON search_queries (query text_pattern_ops)
    """)
    connection.commit()
    cursor.close()
    return_database_connection(connection)

def upsert_queries_batch(queries_with_counts):
    connection = get_database_connection()
    cursor = connection.cursor()
    for query_text, increment_amount in queries_with_counts.items():
        cursor.execute("""
            INSERT INTO search_queries (query, count)
            VALUES (%s, %s)
            ON CONFLICT (query) DO UPDATE
            SET count = search_queries.count + EXCLUDED.count
        """, (query_text, increment_amount))
    connection.commit()
    cursor.close()
    return_database_connection(connection)

def get_top_suggestions(prefix, limit=10):
    connection = get_database_connection()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT query, count FROM search_queries
        WHERE query LIKE %s
        ORDER BY count DESC
        LIMIT %s
    """, (f"{prefix}%", limit))
    results = cursor.fetchall()
    cursor.close()
    return_database_connection(connection)
    
    suggestions = []
    for row in results:
        suggestions.append({"query": row[0], "count": row[1]})
    return suggestions
