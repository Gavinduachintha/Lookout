import psycopg2


connection = psycopg2.connect(
    host = "localhost",
    database = "postgres",
    user = "postgres",
    password = "1234",
    port = "5432"
)

cursor = connection.cursor()

query = "SELECT * FROM bankUsers"
cursor.execute(query)
for row in cursor.fetchall():
    print(row)