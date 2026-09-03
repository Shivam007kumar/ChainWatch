import csv
import ast
from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "hackathon2026")

def create_graph(tx, record):
    tx.run("""
        MERGE (t:Transaction {txid: $txid})
        SET t.timestamp = $timestamp
    """, txid=record['txid'], timestamp=record['timestamp'])

    tx.run("""
        MATCH (t:Transaction {txid: $txid})
        MERGE (sip:IP {ip: $src_ip})
        SET sip.state = $geo_state
        MERGE (dip:IP {ip: $dst_ip})
        MERGE (sip)-[:BROADCASTED {port: $src_port}]->(t)
        MERGE (t)-[:SENT_TO_NODE {port: $dst_port}]->(dip)
    """, src_ip=record['src_ip'], geo_state=record['geo_state'], dst_ip=record['dst_ip'],
         txid=record['txid'], src_port=record['src_port'], dst_port=record['dst_port'])

    inputs = ast.literal_eval(record['input_addresses'])
    in_amounts = ast.literal_eval(record['input_amounts'])
    for wallet, amt in zip(inputs, in_amounts):
        tx.run("""
            MATCH (t:Transaction {txid: $txid})
            MERGE (w:Wallet {address: $wallet})
            MERGE (w)-[:INPUT_TO_TX {amount: $amt}]->(t)
        """, wallet=wallet, txid=record['txid'], amt=amt)

    outputs = ast.literal_eval(record['output_addresses'])
    out_amounts = ast.literal_eval(record['output_amounts'])
    for wallet, amt in zip(outputs, out_amounts):
        tx.run("""
            MATCH (t:Transaction {txid: $txid})
            MERGE (w:Wallet {address: $wallet})
            MERGE (t)-[:OUTPUT_TO_WALLET {amount: $amt}]->(w)
        """, wallet=wallet, txid=record['txid'], amt=amt)

if __name__ == "__main__":
    print("⏳ Connecting to Neo4j and building the graph (This may take a minute for 10k records)...")
    driver = GraphDatabase.driver(URI, auth=AUTH)
    
    with open('synthetic_bitcoin_traffic.csv', 'r') as file:
        reader = csv.DictReader(file)
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n") # Clear old DB
            for row in reader:
                session.execute_write(create_graph, row)
                
    driver.close()
    print("✅ Graph successfully built in Neo4j!")