import sqlite3
import os

DB_NAME = "payroute_payments.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Table 1: Bank & Gateway Nodes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_name TEXT UNIQUE NOT NULL,
            node_type TEXT NOT NULL,
            status TEXT DEFAULT 'ACTIVE'
        )
    """)

    # Table 2: Interbank Routing Edges (Costs, Latency, Reliability)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS routing_edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_node TEXT NOT NULL,
            target_node TEXT NOT NULL,
            cost_inr REAL NOT NULL,
            latency_ms REAL NOT NULL,
            reliability_pct REAL NOT NULL,
            FOREIGN KEY (source_node) REFERENCES payment_nodes(node_name),
            FOREIGN KEY (target_node) REFERENCES payment_nodes(node_name)
        )
    """)

    # Table 3: Transaction Audit Ledger
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transaction_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            amount REAL NOT NULL,
            fraud_status TEXT NOT NULL,
            chosen_route TEXT,
            total_fee REAL,
            latency_ms REAL
        )
    """)

    conn.commit()

    # Seed 7+ Indian Banks and Gateway Network
    cursor.execute("SELECT COUNT(*) FROM payment_nodes")
    if cursor.fetchone()[0] == 0:
        seed_network_data(cursor)
        conn.commit()

    conn.close()

def seed_network_data(cursor):
    nodes = [
        ("Customer", "Origin"),
        ("SBI_Bank", "Bank"),
        ("HDFC_Bank", "Bank"),
        ("ICICI_Bank", "Bank"),
        ("Axis_Bank", "Bank"),
        ("Kotak_Bank", "Bank"),
        ("PNB_Bank", "Bank"),
        ("Bank_of_Baroda", "Bank"),
        ("Razorpay_Gateway", "Gateway"),
        ("NPCI_IMPS_Rail", "ClearingHouse"),
        ("Merchant", "Destination")
    ]
    cursor.executemany("INSERT INTO payment_nodes (node_name, node_type) VALUES (?, ?)", nodes)

    edges = [
        ("Customer", "SBI_Bank", 0.0, 40, 99.8),
        ("Customer", "HDFC_Bank", 0.0, 35, 99.9),
        ("SBI_Bank", "PNB_Bank", 3.0, 140, 96.5),
        ("SBI_Bank", "Bank_of_Baroda", 4.0, 120, 97.0),
        ("SBI_Bank", "Razorpay_Gateway", 1.5, 60, 99.2),
        ("SBI_Bank", "NPCI_IMPS_Rail", 5.0, 25, 99.9),
        ("HDFC_Bank", "ICICI_Bank", 4.5, 110, 98.0),
        ("HDFC_Bank", "Axis_Bank", 3.5, 95, 98.5),
        ("HDFC_Bank", "Razorpay_Gateway", 1.8, 50, 99.4),
        ("PNB_Bank", "Bank_of_Baroda", 2.0, 90, 95.0),
        ("Bank_of_Baroda", "Merchant", 4.0, 110, 96.0),
        ("ICICI_Bank", "Kotak_Bank", 3.0, 85, 97.5),
        ("Axis_Bank", "Kotak_Bank", 2.5, 80, 98.0),
        ("Kotak_Bank", "Merchant", 3.5, 75, 98.8),
        ("Razorpay_Gateway", "Merchant", 2.0, 55, 99.5),
        ("NPCI_IMPS_Rail", "Merchant", 2.5, 20, 99.9)
    ]
    cursor.executemany("""
        INSERT INTO routing_edges (source_node, target_node, cost_inr, latency_ms, reliability_pct)
        VALUES (?, ?, ?, ?, ?)
    """, edges)

def log_transaction(amount, fraud_status, chosen_route="N/A", total_fee=0.0, latency_ms=0.0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transaction_logs (amount, fraud_status, chosen_route, total_fee, latency_ms)
        VALUES (?, ?, ?, ?, ?)
    """, (amount, fraud_status, chosen_route, total_fee, latency_ms))
    conn.commit()
    conn.close()

def get_recent_logs(limit=25):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transaction_logs ORDER BY id DESC LIMIT ?", (limit,))
    logs = cursor.fetchall()
    conn.close()
    return logs