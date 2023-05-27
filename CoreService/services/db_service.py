import pymysql


# connection_settings1 = {
#     'host': 'localhost',
#     'port': 3306,
#     'user': 'your_username',
#     'password': 'your_password',
#     'database': 'your_database_name'
# }

def execute_sql_query(connection_string, query):
    connection = pymysql.connect(connection_string)
    cursor = connection.cursor()

    cursor.execute(query)
    row = cursor.fetchone()  # Fetches a single row
    print(row)

    cursor.close()
    connection.close()

    return row
def execute_rows_query(connection_string, query):
    connection = pymysql.connect(connection_string)
    cursor = connection.cursor()

    cursor.execute(query)
    rows = cursor.fetchall()  # Fetches a single row
    for row in rows:
        print(row)

    cursor.close()
    connection.close()

    return rows

# def execute_sql_query(connection_settings, query):
#     connection = pymysql.connect(
#         host=connection_settings.host,
#         port=connection_settings.port,
#         user=connection_settings.user,
#         password=connection_settings.password,
#         database=connection_settings.database
#     )
#     cursor = connection.cursor()
#
#     cursor.execute(query)
#     row = cursor.fetchone()  # Fetches a single row
#     print(row)
#
#     cursor.close()
#     connection.close()
#
#     return row
