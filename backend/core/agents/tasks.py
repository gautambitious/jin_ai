"""Celery tasks for async tool execution."""

from celery import shared_task
import time
import requests
from typing import Dict, Any
import json


@shared_task(bind=True, name="tools.web_search")
def web_search_task(self, query: str) -> Dict[str, Any]:
    """
    Perform a web search (simulated).
    In production, integrate with actual search APIs.
    """
    time.sleep(1)  # Simulate API call

    # Simulate search results
    results = {
        "query": query,
        "results": [
            {"title": f"Result 1 for {query}", "url": "https://example.com/1"},
            {"title": f"Result 2 for {query}", "url": "https://example.com/2"},
            {"title": f"Result 3 for {query}", "url": "https://example.com/3"},
        ],
        "status": "success",
    }

    return results


@shared_task(bind=True, name="tools.calculate")
def calculate_task(self, expression: str) -> Dict[str, Any]:
    """
    Safely evaluate mathematical expressions.
    """
    try:
        # Use a safe eval for mathematical expressions
        # In production, use a proper math parser
        allowed_chars = set("0123456789+-*/.()")
        if not all(c in allowed_chars or c.isspace() for c in expression):
            return {"error": "Invalid expression", "status": "error"}

        result = eval(expression)
        return {"expression": expression, "result": result, "status": "success"}
    except Exception as e:
        return {"error": str(e), "status": "error"}


@shared_task(bind=True, name="tools.fetch_data")
def fetch_data_task(self, url: str) -> Dict[str, Any]:
    """
    Fetch data from a URL.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        return {
            "url": url,
            "status_code": response.status_code,
            "content": response.text[:1000],  # First 1000 chars
            "status": "success",
        }
    except Exception as e:
        return {"error": str(e), "status": "error"}


@shared_task(bind=True, name="tools.data_analysis")
def data_analysis_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform data analysis (simulated).
    """
    time.sleep(2)  # Simulate processing

    # Simulate analysis
    results = {
        "data_points": len(data) if isinstance(data, (list, dict)) else 0,
        "analysis": "Data processed successfully",
        "summary": f"Analyzed {type(data).__name__} with basic statistics",
        "status": "success",
    }

    return results


@shared_task(bind=True, name="tools.file_operation")
def file_operation_task(
    self, operation: str, filename: str, content: str = ""
) -> Dict[str, Any]:
    """
    Perform file operations (simulated for safety).
    In production, implement with proper file handling and security.
    """
    operations = ["read", "write", "delete", "list"]

    if operation not in operations:
        return {"error": f"Unknown operation: {operation}", "status": "error"}

    # Simulate file operation
    time.sleep(0.5)

    return {
        "operation": operation,
        "filename": filename,
        "message": f"Successfully performed {operation} on {filename}",
        "status": "success",
    }


@shared_task(bind=True, name="tools.database_query")
def database_query_task(self, query: str) -> Dict[str, Any]:
    """
    Execute a database query (simulated).
    In production, use proper database connections.
    """
    time.sleep(1)  # Simulate query execution

    # Simulate query results
    results = {
        "query": query,
        "rows": [
            {"id": 1, "name": "Sample 1", "value": 100},
            {"id": 2, "name": "Sample 2", "value": 200},
        ],
        "count": 2,
        "status": "success",
    }

    return results
