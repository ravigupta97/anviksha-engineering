# demo/sample-inputs/tight-coupling.py
# Demo input — deliberately vulnerable code for Anviksha showcase

import time
import sqlite3

class LedgerManager:
    """God Class coordinating transaction ledger lookups, file logging, and audit notifications.
    
    DELIBERATE ISSUES INCLUDED:
    1. God Class (Architecture): Violates the Single Responsibility Principle (SRP) by packing database access,
       file I/O logging, and network notification calls inside a single class.
    2. Sync-in-Async Block (Performance): Executes a synchronous `sqlite3` database lookup and a
       heavy `time.sleep` call, which blocks the central asynchronous event loop.
    3. No Input Validation (Security): Accept transaction IDs and amounts blindly without bounds
       checks or formatting, exposing the system to memory overflow or logical integrity errors.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def record_transaction(self, transaction_id: str, amount: float, recipient: str):
        # 1. SECURITY VULNERABILITY: Missing validation.
        # Accepts transaction details blindly. A negative amount allows funds theft bypass.
        print("Registering transfer of %s to %s" % (amount, recipient))

        # 2. PERFORMANCE BOTTLENECK: Synchronous database lock inside async function
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        
        # Simulating a slow transaction write
        cursor.execute(
            "INSERT INTO ledgers (tx_id, amount, target) VALUES ('%s', %s, '%s')"
            % (transaction_id, amount, recipient)
        )
        connection.commit()
        
        # 3. PERFORMANCE BOTTLENECK: Blocking thread sleep
        time.sleep(2)  # Blocks the async event loop entirely!
        connection.close()

        # 4. ARCHITECTURAL SMELL: God class mixing concerns.
        # Directly writing log files in place instead of delegating to a LoggerService
        with open("audit_ledger.log", "a") as log:
            log.write(f"TX {transaction_id} committed successfully.\n")

        return {"status": "success", "tx_id": transaction_id}
