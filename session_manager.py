
import time
import json
from typing import Dict, List, Any, Optional
import os
import uuid

class SessionManager:
    def __init__(self, storage_dir="./sessions"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self.active_sessions: Dict[str, Dict] = {} #in memory cache
        
    def get_session_file_path(self, session_id: str) -> str:
        return os.path.join(self.storage_dir, f"{session_id}.json")
    
    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        session_data = {
            "created_at": time.time(),
            "last_access": time.time(),
            "conversation_history": [],
            "schema_cache": None
        }
        
        self.active_sessions[session_id] = session_data
        self.save_session(session_id, session_data)
        return session_id
    
    def save_session(self, session_id: str, session_data: Dict) -> None:
        with open(self.get_session_file_path(session_id), 'w') as f:
            json.dump(session_data, f)
    
    def get_session(self, session_id: str) -> Optional[Dict]:

        if session_id in self.active_sessions:
            session_data = self.active_sessions[session_id]
            session_data["last_access"] = time.time()
            return session_data
        
        file_path = self.get_session_file_path(session_id)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    session_data = json.load(f)
                    session_data["last_access"] = time.time()
                    # Add to memory cache
                    self.active_sessions[session_id] = session_data
                    return session_data
            except json.JSONDecodeError:
                return None
        
        return None
    
    def update_session(self, session_id: str, 
                      question: str = None, 
                      sql_query: str = None, 
                      results: List[Dict] = None, 
                      answer: str = None,
                      schema_cache: Dict = None) -> bool:
     
        session_data = self.get_session(session_id)
        if not session_data:
            return False
        
        session_data["last_access"] = time.time()
        
        if question:
            conversation_entry = {
                "timestamp": time.time(),
                "question": question,
                "sql_query": sql_query,
                "answer": answer,
                "results_summary": f"{len(results)} rows returned" if results else None
            }
            session_data["conversation_history"].append(conversation_entry)
        
        if schema_cache:
            session_data["schema_cache"] = schema_cache
            
        self.save_session(session_id, session_data)
        self.active_sessions[session_id] = session_data
        
        return True
    
    def get_conversation_history(self, session_id: str) -> List[Dict]:

        session_data = self.get_session(session_id)
        if not session_data:
            return []
        
        return session_data.get("conversation_history", [])
    
    def get_schema_cache(self, session_id: str) -> Optional[Dict]:

        session_data = self.get_session(session_id)
        if not session_data:
            return None
        
        return session_data.get("schema_cache")
    
    def clean_old_sessions(self, max_age_hours: int = 24) -> int:

        max_age_seconds = max_age_hours * 3600
        current_time = time.time()
        cleaned_count = 0
        
        for filename in os.listdir(self.storage_dir):
            if not filename.endswith('.json'): 
                continue
                
            file_path = os.path.join(self.storage_dir, filename)
            try:
                with open(file_path, 'r') as f:
                    session_data = json.load(f)
                    last_access = session_data.get("last_access", 0)
                    
                    if current_time - last_access > max_age_seconds:
                        os.remove(file_path)
                        session_id = filename.replace('.json', '')
                        if session_id in self.active_sessions:
                            del self.active_sessions[session_id]
                        cleaned_count += 1
            except (json.JSONDecodeError, IOError):
                os.remove(file_path)
                cleaned_count += 1
                
        return cleaned_count