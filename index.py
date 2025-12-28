import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from scripts.execute_hervens import execute_query_api
from fastapi import FastAPI

app = FastAPI()

@app.get("/search")
async def search(query: str, limit: int = 10):
    """
    Search endpoint for Hervens database.
    Query: the search query string
    Limit: maximum number of results (default 10)
    """
    return execute_query_api(query, limit)