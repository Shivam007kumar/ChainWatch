import csv
import ast
from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "hackathon2026")

def create_graph(tx, record):
    # 1. Create the Transaction Node
    tx.run("""
        MERGE (t:Transaction {txid: $txid})
        SET t.timestamp = $timestamp
    """, txid=record['txid'], timestamp=record['timestamp'])

    # 2. Match Tx, Create IP Nodes & Link them
    tx.run("""
        MATCH (t:Transaction {txid: $txid})
        MERGE (sip:IP {ip: $src_ip})
        SET sip.country = $geo_country
        MERGE (dip:IP {ip: $dst_ip})
        MERGE (sip)-[:BROADCASTED {port: $src_port}]->(t)
        MERGE (t)-[:SENT_TO_NODE {port: $dst_port}]->(dip)
    """, src_ip=record['src_ip'], geo_country=record['geo_country'], dst_ip=record['dst_ip'],
         txid=record['txid'], src_port=record['src_port'], dst_port=record['dst_port'])

    # 3. Create Input Wallets & Link to Transaction
    inputs = ast.literal_eval(record['input_addresses'])
    in_amounts = ast.literal_eval(record['input_amounts'])
    for wallet, amt in zip(inputs, in_amounts):
        tx.run("""
            MATCH (t:Transaction {txid: $txid})
            MERGE (w:Wallet {address: $wallet})
            MERGE (w)-[:INPUT_TO_TX {amount: $amt}]->(t)
        """, wallet=wallet, txid=record['txid'], amt=amt)

    # 4. Create Output Wallets & Link to Transaction
    outputs = ast.literal_eval(record['output_addresses'])
    out_amounts = ast.literal_eval(record['output_amounts'])
    for wallet, amt in zip(outputs, out_amounts):
        tx.run("""
            MATCH (t:Transaction {txid: $txid})
            MERGE (w:Wallet {address: $wallet})
            MERGE (t)-[:OUTPUT_TO_WALLET {amount: $amt}]->(w)
        """, wallet=wallet, txid=record['txid'], amt=amt)

if __name__ == "__main__":
    print("⏳ Connecting to Neo4j and building the graph...")
    driver = GraphDatabase.driver(URI, auth=AUTH)
    
    with open('synthetic_bitcoin_traffic.csv', 'r') as file:
        reader = csv.DictReader(file)
        with driver.session() as session:
            # Clear old data (good for testing)
            session.run("MATCH (n) DETACH DELETE n")
            
            for row in reader:
                session.execute_write(create_graph, row)
                
    driver.close()
    print("✅ Graph successfully built in Neo4j!")