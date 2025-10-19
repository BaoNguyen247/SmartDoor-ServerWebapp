import MySQLdb
from MySQLdb import Error
import bcrypt

def init_user_database():
    connection = None
    try:
        # Connect to MySQL as root with auth_socket
        connection = MySQLdb.connect(
            host="localhost",
            user="root",
            passwd=""  # Empty string for auth_socket
        )
        cursor = connection.cursor()

        # Create database
        cursor.execute("CREATE DATABASE IF NOT EXISTS user_auth_db")
        print("Database 'user_auth_db' created or already exists")

        # Switch to the database
        cursor.execute("USE user_auth_db")

        # Create auth_user
        cursor.execute(
            "CREATE USER IF NOT EXISTS 'auth_user'@'localhost' IDENTIFIED WITH mysql_native_password BY 'Y9#nM2$pL8xQ7vR'"
        )
        print("User 'auth_user' created or already exists")

        # Grant privileges to auth_user
        cursor.execute("GRANT ALL PRIVILEGES ON user_auth_db.* TO 'auth_user'@'localhost'")
        cursor.execute("FLUSH PRIVILEGES")
        print("Privileges granted to 'auth_user'")

        # Create users table
        create_table_query = """
        CREATE TABLE IF NOT EXISTS users (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        cursor.execute(create_table_query)
        print("Table 'users' created or already exists")

        # Hash a test password using bcrypt
        test_password = "TestP@ssw0rd123"
        hashed_password = bcrypt.hashpw(test_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Insert a test user
        test_insert_query = """
        INSERT INTO users (username, password) VALUES (%s, %s)
        """
        test_data = ("testuser", hashed_password)
        cursor.execute(test_insert_query, test_data)
        connection.commit()
        print("Test user inserted")

        # Verify table contents
        cursor.execute("SELECT id, username, created_at FROM users")
        results = cursor.fetchall()
        print("Table contents:", results)

    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection and connection.open:
            cursor.close()
            connection.close()
            print("MySQL connection closed")

if __name__ == "__main__":
    init_user_database()