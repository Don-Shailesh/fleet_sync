import mysql.connector
from mysql.connector import Error, errorcode
from config import Config

def get_connection(include_db=True):
    """
    Establish a connection to the MySQL server.
    If include_db is True, connects directly to Config.MYSQL_DB.
    """
    params = {
        'host': Config.MYSQL_HOST,
        'port': Config.MYSQL_PORT,
        'user': Config.MYSQL_USER,
        'password': Config.MYSQL_PASSWORD,
        'charset': 'utf8mb4',
        'use_pure': True
    }
    if include_db:
        params['database'] = Config.MYSQL_DB

    return mysql.connector.connect(**params)

def query_db(query, params=(), one=False, commit=False):
    """
    Execute a parameterized SQL query safely.
    Returns:
      - dict (if one=True)
      - list of dicts (if one=False and select query)
      - lastrowid (if commit=True and INSERT)
      - affected row count (if commit=True and UPDATE/DELETE)
    """
    conn = None
    cursor = None
    try:
        conn = get_connection(include_db=True)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params)

        if commit:
            conn.commit()
            last_id = cursor.lastrowid
            row_count = cursor.rowcount
            return last_id if last_id else row_count

        result = cursor.fetchall()
        return (result[0] if result else None) if one else result

    except Error as e:
        if conn and commit:
            conn.rollback()
        raise e
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def check_db_health():
    """
    Verifies connection to MySQL and checks if fleetsync_db exists.
    Returns (status: bool, message: str)
    """
    try:
        conn = get_connection(include_db=False)
        cursor = conn.cursor()
        cursor.execute(f"SHOW DATABASES LIKE '{Config.MYSQL_DB}'")
        exists = cursor.fetchone() is not None
        cursor.close()
        conn.close()

        if exists:
            return True, f"Connected to MySQL on {Config.MYSQL_HOST}:{Config.MYSQL_PORT} (Database '{Config.MYSQL_DB}' active)"
        else:
            return False, f"MySQL server is running, but database '{Config.MYSQL_DB}' has not been initialized yet. Run 'python setup_db.py'."
    except Error as e:
        return False, f"Cannot connect to MySQL server at {Config.MYSQL_HOST}:{Config.MYSQL_PORT}. Make sure XAMPP MySQL is started. Error: {str(e)}"
