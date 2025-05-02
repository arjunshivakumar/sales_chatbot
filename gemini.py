import os
from google import genai
from dotenv import load_dotenv  

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("Google API key not found. Set it in .env or environment variables.")

# genai.configure(api_key=api_key)

client = genai.Client(api_key=api_key)

def generate_sql_from_gemini(question: str, table_schema: str) -> str:
    prompt = f"""
    You are a skilled data analyst. Given the following sales data table schema: 
    {table_schema}

    A user has asked the following question:
    '{question}'

    Please write the PostrgreSQL query that would answer this question.
    """

    response = client.models.generate_content(
        model="gemini-2.0-flash", contents=prompt
    )
    
    sql_query = response.text.strip()
    sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
    
    return sql_query


def ask_gemini(prompt: str) -> str:
    response = client.models.generate_content(
        model="gemini-2.0-flash", contents=prompt
    )    
    return response.text
