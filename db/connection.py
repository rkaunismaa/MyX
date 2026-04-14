import mysql.connector


def get_connection(config: dict) -> mysql.connector.MySQLConnection:
    db = config["database"]
    return mysql.connector.connect(
        host=db["host"],
        port=db["port"],
        database=db["name"],
        user=db["user"],
        password=db["password"],
    )


def get_enabled_targets(conn) -> list[dict]:
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM scrape_targets WHERE enabled = TRUE ORDER BY target_id")
    targets = cursor.fetchall()
    cursor.close()
    return targets
