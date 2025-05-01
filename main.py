from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from db import run_query
from gemini import generate_sql_from_gemini, ask_gemini

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3002"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskRequest(BaseModel):
    question: str
    session_id: str

TABLE_SCHEMA = """
coffee_sales (
    date DATE,
    datetime TIMESTAMP,
    cash_type VARCHAR,
    card VARCHAR,
    money DECIMAL,
    coffee_name VARCHAR
)
"""

@app.post("/ask")
async def ask(request: AskRequest):
    print(request.question)
    sql_query = generate_sql_from_gemini(request.question, TABLE_SCHEMA)
    if not sql_query:
        return {"error": "Gemini could not generate SQL for the question."}

    result = run_query(sql_query)

    prompt_for_answer = f"""
    The user asked: '{request.question}'
    Here is the SQL query result:
    {result}

    Please summarize the answer in a natural language response.
    """

    answer = ask_gemini(prompt_for_answer)
    print({
        "question": request.question,
        "sql_query": sql_query,
        "data": result,
        "gemini_answer": answer
    })
    return {
        "question": request.question,
        "sql_query": sql_query,
        "data": result,
        "gemini_answer": answer
    }
