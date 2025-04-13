# Run this script to add new columns and tables to your database
# Save this as db_upgrade.py and run it separately

import sqlite3
import os

# Use the same DB_PATH as in your app.py
DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'hotel.db')

def upgrade_database():
    print("Starting database upgrade...")
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Add phone column to users table if it doesn't exist
        try:
            c.execute("ALTER TABLE users ADD COLUMN phone TEXT")
            print("Added phone column to users table")
        except sqlite3.OperationalError:
            print("Phone column already exists in users table")
        
        # Create favorites table
        c.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                hotel_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (hotel_id) REFERENCES hotels(id),
                UNIQUE(user_id, hotel_id)
            )
        ''')
        print("Created favorites table")
        
        # Create hotel_ratings table
        c.execute('''
            CREATE TABLE IF NOT EXISTS hotel_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hotel_id INTEGER,
                user_id INTEGER,
                rating INTEGER,
                review TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (hotel_id) REFERENCES hotels(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        print("Created hotel_ratings table")
        
        conn.commit()
    
    print("Database upgrade completed successfully!")

if __name__ == "__main__":
    upgrade_database()