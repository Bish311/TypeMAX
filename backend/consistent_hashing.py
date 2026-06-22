import hashlib

def get_assigned_node(prefix: str, total_nodes: int = 3) -> int:
    hash_value = int(hashlib.md5(prefix.encode('utf-8')).hexdigest(), 16)
    return hash_value % total_nodes
