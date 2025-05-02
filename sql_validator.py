
import sqlparse
from sqlparse.sql import TokenList, Identifier, Function, Parenthesis, Where
from sqlparse.tokens import DML, Keyword, Name
import re

# Reserved keywords and functions that shouldn't be mistaken for table references
PG_KEYWORDS_AND_FUNCTIONS = {
    'SELECT', 'FROM', 'WHERE', 'JOIN', 'ON', 'AND', 'OR', 'NOT', 'GROUP', 'BY', 
    'HAVING', 'ORDER', 'LIMIT', 'OFFSET', 'AS', 'IN', 'BETWEEN', 'LIKE', 'IS', 
    'NULL', 'TRUE', 'FALSE', 'ASC', 'DESC', 'DISTINCT', 'CASE', 'WHEN', 'THEN', 
    'ELSE', 'END', 'EXTRACT', 'DATE_PART', 'CAST', 'TO_CHAR', 'TO_DATE', 'NOW',
    'CURRENT_DATE', 'CURRENT_TIME', 'CURRENT_TIMESTAMP', 'COALESCE', 'NULLIF',
    'AVG', 'COUNT', 'MAX', 'MIN', 'SUM', 'ROUND', 'LOWER', 'UPPER', 'CONCAT',
    'SUBSTRING', 'TRIM', 'LTRIM', 'RTRIM', 'LENGTH', 'DATE_TRUNC', 'INTERVAL',
    'YEAR', 'MONTH', 'DAY', 'HOUR', 'MINUTE', 'SECOND', 'WEEK', 'QUARTER'
}

def is_safe_select_query(sql):
    try:
        parsed = sqlparse.parse(sql)
        if len(parsed) != 1:
            return False, "Multiple SQL statements detected"
        
        stmt = parsed[0]
        stmt_type = stmt.get_type()

        if stmt_type != 'SELECT':
            return False, f"Only SELECT queries are allowed, found: {stmt_type}"

        # Check for dangerous keywords anywhere in the query
        def extract_keywords(token_list):
            keywords = []
            for token in token_list.tokens:
                if isinstance(token, TokenList):
                    keywords.extend(extract_keywords(token))
                elif token.ttype in (DML, Keyword):
                    keywords.append(token.value.upper())
            return keywords

        all_keywords = extract_keywords(stmt)

        forbidden_keywords = {
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'TRUNCATE',
            'GRANT', 'REVOKE', 'MERGE', 'EXEC', 'EXECUTE', 'CALL', 'CREATE',
            'SET', 'USE', 'SAVEPOINT', 'TRANSACTION', 'ROLLBACK', 'COMMIT'
        }

        for keyword in all_keywords:
            if keyword in forbidden_keywords:
                return False, f"Forbidden keyword detected: {keyword}"
        
        dangerous_functions = [
            'pg_read_file', 'pg_read_binary_file', 'pg_ls_dir', 'pg_sleep',
            'dblink', 'dblink_exec', 'lo_import', 'lo_export',
            'copy', 'system', 'exec', 'execute', 'xp_cmdshell'
        ]
        
        functions = []
        def extract_functions(token_list):
            for token in token_list.tokens:
                if isinstance(token, Function):
                    function_name = ''
                    for t in token.tokens:
                        if t.ttype is Name or t.ttype is Name.Function:
                            function_name = t.value.lower()
                            break
                    if function_name:
                        functions.append(function_name)
                
                if isinstance(token, TokenList):
                    extract_functions(token)
        
        extract_functions(stmt)
        
        for func in functions:
            if func.lower() in dangerous_functions:
                return False, f"Dangerous function detected: {func}"
        
        if "--" in sql or "/*" in sql or "*/" in sql:
            return False, "SQL comments are not allowed"
        
        if ";" in sql and not sql.strip().endswith(";"):
            return False, "Unexpected semicolon detected"


        def validate_where_clause(token_list):
            for token in token_list.tokens:
                if isinstance(token, Where):
                    where_text = token.value.lower()
                    tautology_pattern = re.compile(r"['\"]\s*\w+\s*['\"](\s*=\s*)['\"]\s*\w+\s*['\"]")
                    if tautology_pattern.search(where_text):
                        return False, "Suspicious tautology detected in WHERE clause"
                
                if isinstance(token, TokenList):
                    result, msg = validate_where_clause(token)
                    if not result:
                        return result, msg
            
            return True, ""
        
        where_result, where_msg = validate_where_clause(stmt)
        if not where_result:
            return where_result, where_msg
        
        return True, "Query is valid"

    except Exception as e:
        return False, f"Error during SQL safety check: {e}"

def extract_table_references(sql):

    try:
        parsed = sqlparse.parse(sql)
        if len(parsed) != 1:
            return set()
        
        stmt = parsed[0]
        
        referenced_tables = set()
        
        in_from_clause = False
        in_join_clause = False
        table_context = None
        
        for token in stmt.tokens:
            # Identify FROM and JOIN clauses
            if token.ttype is Keyword and token.value.upper() == 'FROM':
                in_from_clause = True
                table_context = 'FROM'
                continue
            elif token.ttype is Keyword and ('JOIN' in token.value.upper()):
                in_join_clause = True
                table_context = 'JOIN'
                continue
            
            # Process table references in FROM and JOIN clauses
            if (in_from_clause or in_join_clause) and token.ttype is None:
                if token.value.upper() in ('WHERE', 'GROUP', 'HAVING', 'ORDER', 'LIMIT'):
                    in_from_clause = False
                    in_join_clause = False
                    table_context = None
                    continue
                    
                if token.value.strip() in (',', ''):
                    continue
                    
                # Process table reference
                id_value = token.value.strip()
                
                # Handle "table_name AS alias" or "table_name alias"
                parts = re.split(r'\s+(?:as\s+)?', id_value, flags=re.IGNORECASE, maxsplit=1)
                if parts:
                    table_name = parts[0].lower().strip('"`[] ')
                    
                    if table_name.upper() in PG_KEYWORDS_AND_FUNCTIONS:
                        continue
                    
                    if table_name.startswith('('):
                        continue
                        
                    referenced_tables.add(table_name)
                    
                if table_context == 'FROM':
                    in_from_clause = False
                elif table_context == 'JOIN':
                    in_join_clause = False
                table_context = None
        
        #Check for functions that might be mistakenly identified as tables
        function_names = set()
        def extract_functions(token_list):
            for token in token_list.tokens:
                if isinstance(token, Function):
                    function_name = ''
                    for t in token.tokens:
                        if t.ttype is Name or t.ttype is Name.Function:
                            function_name = t.value.lower()
                            break
                    if function_name:
                        function_names.add(function_name)
                
                if isinstance(token, TokenList):
                    extract_functions(token)
        
        extract_functions(stmt)
        
        referenced_tables = referenced_tables - function_names
        
        return referenced_tables
    
    except Exception as e:
        print(f"Error extracting table references: {e}")
        return set()

def validate_query_against_schema(sql, schema):
    try:
        referenced_tables = extract_table_references(sql)
        
        if not referenced_tables:
            return True, "No table references detected"
        
        schema_tables = {table_name.lower() for table_name in schema.keys()}
        
        for table in referenced_tables:
            if table.upper() in PG_KEYWORDS_AND_FUNCTIONS:
                continue
                
            if table not in schema_tables:
                potential_matches = [t for t in schema.keys() if t.lower() == table.lower()]
                if potential_matches:
                    return False, f"Referenced table '{table}' does not match case. Did you mean '{potential_matches[0]}'?"
                return False, f"Referenced table '{table}' does not exist in schema"
        
        return True, "Query references valid schema objects"
        
    except Exception as e:
        print(f"Schema validation error: {e}")
        return False, f"Error validating query against schema: {e}"

def validate_sql_query(sql, schema=None):

    is_safe, message = is_safe_select_query(sql)
    if not is_safe:
        return False, message
    
    if schema:
        is_valid_schema, schema_message = validate_query_against_schema(sql, schema)
        if not is_valid_schema:
            return False, schema_message
    
    return True, "Query is valid and safe"