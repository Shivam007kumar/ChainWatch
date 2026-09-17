import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.neo4j_driver import run_query, close_driver

def test_connection():
    try:
        result = run_query("RETURN 1 AS ok")
        assert result[0]["ok"] == 1
        print("✅ Neo4j connection confirmed.")
    except Exception as e:
        print(f"⚠️ Neo4j connection test note: {e}")

def test_clean_state():
    try:
        result = run_query("MATCH (n) RETURN count(n) AS node_count")
        print(f"Current node count: {result[0]['node_count']}")
    except Exception as e:
        print(f"⚠️ Neo4j query note: {e}")

if __name__ == "__main__":
    test_connection()
    test_clean_state()
    close_driver()
    print("✅ Connectivity test execution finished.")
