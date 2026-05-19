# demo/sample-inputs/sql-injection.py
# Demo input — deliberately vulnerable code for Anviksha showcase

from database import DatabaseConnection

class UserService:
    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection

    def get_user_by_name(self, username: str):
        """Fetches user account details matching the supplied name.
        
        DELIBERATE ISSUES INCLUDED:
        1. SQL Injection: Raw string formatting interpolates user inputs directly into the query,
           allowing attackers to bypass authentication or drop tables.
        2. Performance (Missing Index): Query is executed against the 'name' column which lacks
           a database index, forcing PostgreSQL to perform a full-table scan on every lookup.
        """
        # CRITICAL VULNERABILITY: Raw string interpolation
        query = "SELECT id, email, role FROM users WHERE name = '%s'" % username
        
        # Execute query directly
        result = self.db.execute_raw(query)
        
        if len(result) > 0:
            return result[0]
        return None
