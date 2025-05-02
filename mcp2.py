import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import sqlparse
from sql_validator import validate_sql_query
from session_manager import SessionManager
from typing import Optional
from fastapi.background import BackgroundTasks
import time

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("Google API key not found. Set it in .env or environment variables.")

client = genai.Client(api_key=api_key)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize session manager
session_manager = SessionManager()

# Schedule periodic cleanup
def cleanup_old_sessions():
    session_manager.clean_old_sessions(max_age_hours=24)

class AskRequest(BaseModel):
    question: str
    session_id: Optional[str] = None  # Now optional

class SessionResponse(BaseModel):
    session_id: str

def get_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )

def fetch_database_schema():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    tables = [record['table_name'] for record in cursor.fetchall()]
    
    schema = {}
    
    # For each table, get its columns
    for table in tables:
        # Get columns and data types
        cursor.execute(f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = '{table}'
        """)
        columns = {record['column_name']: record['data_type'] for record in cursor.fetchall()}
        
        schema[table] = {
            "columns": columns,
            "foreign_keys": []
        }
    
    # Get foreign key relationships
    cursor.execute("""
        SELECT
            tc.table_name AS table_name,
            kcu.column_name AS column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM
            information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
    """)
    
    for record in cursor.fetchall():
        table_name = record['table_name']
        if table_name in schema:
            schema[table_name]["foreign_keys"].append({
                "column": record['column_name'],
                "references_table": record['foreign_table_name'],
                "references_column": record['foreign_column_name']
            })
    
    cursor.close()
    conn.close()
    return schema

def run_query(sql):
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(sql)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return results
    except Exception as e:
        print(f"Error executing SQL: {e}")
        raise HTTPException(status_code=400, detail=f"SQL query error: {str(e)}")


def generate_sql_query(question, schema, session_id=None):
    schema_json = json.dumps(schema, indent=2)
    
    # Get conversation history if session_id is provided
    conversation_history = []
    if session_id:
        conversation_history = session_manager.get_conversation_history(session_id)
    
    # Format the conversation history for the prompt
    conversation_context = ""
    if conversation_history:
        # Include up to the last 5 interactions to avoid prompt getting too large
        recent_conversations = conversation_history[-5:]
        conversation_context = "Previous conversation:\n"
        for idx, conv in enumerate(recent_conversations):
            conversation_context += f"Question {idx+1}: {conv['question']}\n"
            conversation_context += f"SQL Query {idx+1}: {conv['sql_query']}\n"
            conversation_context += f"Answer {idx+1}: {conv['answer']}\n\n"
    
    prompt = f"""
    You are a database expert with deep knowledge in SQL. Given the following database schema:

    {schema_json}

    {conversation_context}
    
    A user has asked the following question:
    '{question}'

    Your task:

    1. Analyze which tables and relationships are relevant to answer this question
    2. Create a PostgreSQL SELECT query (never INSERT, UPDATE, DELETE, or DROP) that:
       - Uses only relevant table(s)
       - Joins related tables using foreign key relationships when needed
       - Selects only necessary columns
       - Includes WHERE, GROUP BY, or ORDER BY if appropriate
       
    3. If the user's question refers to previous conversations or seems to be a follow-up question, 
       make sure to consider the context from previous interactions.

    RULES:
    - Output ONLY the SQL query (no explanation or code block)
    - Do NOT use INSERT, UPDATE, DELETE, DROP, ALTER, or any write operations
    - The SQL must be valid PostgreSQL
    """

    response = client.models.generate_content(
        model="gemini-2.0-flash", contents=prompt
    )

    sql_query = response.text.strip().replace("```sql", "").replace("```", "").strip()

    # Apply the advanced validation using our new validator
    is_valid, validation_message = validate_sql_query(sql_query, schema)
    
    if not is_valid:
        print(f"[BLOCKED UNSAFE SQL] Generated query: {sql_query}")
        print(f"Validation error: {validation_message}")
        raise HTTPException(
            status_code=400,
            detail=(
                f"Sorry, we could not generate a safe SQL query for your question. "
                f"Validation error: {validation_message}. "
                "Please try rephrasing your question."
            )
        )
    
    return sql_query


def explain_sql_query(question, sql_query, schema, session_id=None):
    schema_json = json.dumps(schema, indent=2)
    
    # Get conversation history if session_id is provided
    conversation_history = []
    if session_id:
        conversation_history = session_manager.get_conversation_history(session_id)
    
    # Format recent conversation context
    conversation_context = ""
    if conversation_history:
        # Include just the last interaction to keep the context focused
        last_conversation = conversation_history[-1]
        conversation_context = "This question may be related to previous conversations.\n"
        conversation_context += f"Previous question: {last_conversation['question']}\n"
        conversation_context += f"Previous SQL query: {last_conversation['sql_query']}\n\n"
    
    prompt = f"""
    Given the following database schema:
    
    {schema_json}
    
    {conversation_context}
    
    And the user question:
    '{question}'
    
    Please explain why the following SQL query is appropriate to answer this question:
    
    ```sql
    {sql_query}
    ```
    
    Explain:
    1. Which tables were selected and why
    2. How the relationships between tables are being used (if any joins)
    3. What specific columns are being selected and why
    4. Any filters, aggregations, or other operations being applied
    
    Keep the explanation concise but informative.
    """

    response = client.models.generate_content(
        model="gemini-2.0-flash", contents=prompt
    )
    
    return response.text.strip()

def summarize_results(question, sql_query, results, session_id=None):
    # Get conversation history if session_id is provided
    conversation_history = []
    if session_id:
        conversation_history = session_manager.get_conversation_history(session_id)
    
    # Format the conversation context
    conversation_context = ""
    if conversation_history:
        # Include the last conversation for context if it exists
        last_conversation = conversation_history[-1]
        conversation_context = "Consider this may be a follow-up to a previous question:\n"
        conversation_context += f"Previous question: {last_conversation['question']}\n"
        conversation_context += f"Previous answer: {last_conversation['answer']}\n\n"
    
    prompt = f"""
    {conversation_context}
    
    The user asked: '{question}'
    
    SQL query used:
    ```sql
    {sql_query}
    ```
    
    Here are the query results:
    {json.dumps(results, default=str)}
    
    Please provide a comprehensive but concise natural language summary of these results that directly answers the user's question. 
    Include relevant numbers and trends if present.
    
    If this appears to be a follow-up to previous questions, maintain continuity in your response.
    """

    response = client.models.generate_content(
        model="gemini-2.0-flash", contents=prompt
    )
    
    return response.text.strip()

# FastAPI endpoints
@app.get("/schema")
async def get_schema():
    try:
        schema = fetch_database_schema()
        return {"schema": schema}
    except Exception as e:
        return {"error": str(e)}

@app.post("/session")
async def create_session():
    """Create a new session and return the session ID"""
    session_id = session_manager.create_session()
    return {"session_id": session_id}

@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session information"""
    session_data = session_manager.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Return only the safe parts of the session data
    return {
        "session_id": session_id,
        "created_at": session_data.get("created_at"),
        "conversation_history": session_data.get("conversation_history")
    }

@app.post("/ask")
async def ask(request: AskRequest, background_tasks: BackgroundTasks):
    # Create a new session if none provided
    session_id = request.session_id
    if not session_id:
        session_id = session_manager.create_session()
    elif not session_manager.get_session(session_id):
        # If provided session doesn't exist, create it
        session_id = session_manager.create_session()
    
    # Try to get schema from cache first
    schema = session_manager.get_schema_cache(session_id)
    
    # If not in cache, fetch from database
    if not schema:
        try:
            schema = fetch_database_schema()
            # Cache the schema for future use
            session_manager.update_session(session_id, schema_cache=schema)
        except Exception as e:
            raise HTTPException(status_code=500, detail="Could not fetch database schema.")

    try:
        sql_query = generate_sql_query(request.question, schema, session_id)
    except HTTPException as e:
        raise e  # Already handled in generate_sql_query
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error generating SQL query.")

    try:
        results = run_query(sql_query)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error executing SQL query.")

    try:
        sql_explanation = explain_sql_query(request.question, sql_query, schema, session_id)
        answer = summarize_results(request.question, sql_query, results, session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error generating explanation or summary.")
    
    # Update session with the new conversation
    session_manager.update_session(
        session_id, 
        question=request.question,
        sql_query=sql_query,
        results=results,
        answer=answer
    )
    
    # Schedule cleanup of old sessions
    background_tasks.add_task(cleanup_old_sessions)
    
    return {
        "session_id": session_id,
        "question": request.question,
        "sql_query": sql_query,
        "sql_explanation": sql_explanation,
        "data": results,
        "answer": answer
    }


# Run with: uvicorn main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)