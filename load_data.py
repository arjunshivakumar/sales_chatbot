import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()

df = pd.read_csv("coffee_sales.csv")

df['date'] = pd.to_datetime(df['date']).dt.date
df['datetime'] = pd.to_datetime(df['datetime'])

conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
)
cursor = conn.cursor()

for _, row in df.iterrows():
    cursor.execute("""
        INSERT INTO coffee_sales (date, datetime, cash_type, card, money, coffee_name)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (row['date'], row['datetime'], row['cash_type'], row['card'], row['money'], row['coffee_name']))

conn.commit()
cursor.close()
conn.close()

print("Data inserted successfully.")
