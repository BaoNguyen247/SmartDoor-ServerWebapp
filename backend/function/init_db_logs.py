import MySQLdb
from MySQLdb import Error

def init_database():
    connection = None
    try:
        # Connect to MySQL as root (run with sudo)
        connection = MySQLdb.connect(
            host="localhost",
            user="root",
            passwd=""
        )
        cursor = connection.cursor()
        
        # --- Khởi tạo Database và User ---
        cursor.execute("CREATE DATABASE IF NOT EXISTS smart_lock_db")
        print("Database 'smart_lock_db' created or already exists")
        cursor.execute("USE smart_lock_db")
        cursor.execute(
            "CREATE USER IF NOT EXISTS 'backend_user'@'localhost' IDENTIFIED WITH mysql_native_password BY 'Workfromhome247@'"
        )
        cursor.execute("GRANT ALL PRIVILEGES ON smart_lock_db.* TO 'backend_user'@'localhost'")
        cursor.execute("FLUSH PRIVILEGES")
        print("User and Privileges setup complete")
        
        # --- Xóa bảng cũ (Đảm bảo cấu trúc mới được áp dụng) ---
        cursor.execute("DROP TABLE IF EXISTS smart_lock_logs")
        print("Dropped existing table 'smart_lock_logs' (to apply new structure)")
        
        # --- Tạo bảng mới: Chỉ sử dụng một cột 'timestamp' duy nhất tự động gán thời gian hiện tại ---
        create_table_query = """
        CREATE TABLE smart_lock_logs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            -- Cột 'timestamp' duy nhất, tự động lưu thời gian tạo bản ghi
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, 
            event_type ENUM('OPEN', 'LOCKSYSTEM', 'ALERT') NOT NULL,
            name VARCHAR(255),
            INDEX idx_timestamp (timestamp)
        )
        """
        cursor.execute(create_table_query)
        print("Table 'smart_lock_logs' created with a single, auto-populating 'timestamp' column.")

        # Insert a test record (không cần truyền giá trị cho timestamp)
        test_insert_query = """
        INSERT INTO smart_lock_logs (event_type, name) VALUES (%s, %s)
        """
        test_data = ("OPEN", "Auto Time Test")
        cursor.execute(test_insert_query, test_data)
        connection.commit()
        print("Test record inserted (timestamp populated automatically)")

        # Verify table contents
        cursor.execute("SELECT * FROM smart_lock_logs")
        results = cursor.fetchall()
        print("Table contents (ID, Timestamp, Event Type, Name):", results)

    except Error as e:
        print(f"Error: {e}")
    finally:
        if connection and connection.open:
            cursor.close()
            connection.close()
            print("MySQL connection closed")

if __name__ == "__main__":
    init_database()

#sudo ~/esp32project/SmartlockServerWeb/backend/venv/bin/python3 init.py