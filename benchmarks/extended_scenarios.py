"""
Extended Benchmark Scenarios - 8 scenarios covering more edge cases
Complements the base 4 scenarios.
"""

EXTENDED_BENCHMARKS = [
    {
        "id": "scenario_5_api_rate_limit",
        "category": "Resource & Priority / Rate Limiting",
        "name": "High-Concurrency API under Rate Limits",
        "requirements": """
        Build a REST API that handles 10k requests per second with rate limiting.
        Endpoints: GET /users, POST /users, GET /users/{id}, PUT /users/{id}, DELETE /users/{id}
        Must include Pydantic validation, JWT authentication, and 429 throttling.
        """,
        "project_context": "Python FastAPI with Redis rate limiting",
        "constraints": "Token budget limited to 4000, must respect API rate limits"
    },
    {
        "id": "scenario_6_data_pipeline",
        "category": "Integration & DAG Orchestration",
        "name": "ETL Pipeline with DAG Dependencies",
        "requirements": """
        Build an ETL pipeline: Extract from PostgreSQL, Transform with data cleaning,
        Load to data warehouse. Tasks: extract_users, extract_orders (parallel), 
        transform_join (depends on both extracts), load_warehouse (depends on transform).
        Include monitoring and retry logic.
        """,
        "project_context": "Data engineering platform with Airflow-like DAG",
        "constraints": "Must generate valid DAG with no circular dependencies"
    },
    {
        "id": "scenario_7_empty_input",
        "category": "Failure Handling & Edge Cases",
        "name": "Empty / Vague Requirements Edge Case",
        "requirements": "Build something cool.",
        "project_context": "Generic web app",
        "constraints": "Should request clarification, not hallucinate"
    },
    {
        "id": "scenario_8_long_context",
        "category": "Context Hygiene & Window Management",
        "name": "Very Long Context with Repetition",
        "requirements": """
        Build a task management app.
        Build a task management app.
        Build a task management app. (repeated 20 times for noise)
        
        Features:
        - User auth with JWT
        - CRUD for tasks
        - Due dates
        - Priority levels
        
        Traceback (most recent call last):
          File "app.py", line 100, in <module>
          Exception: Dummy error for noise testing
          File "app.py", line 101, in <module>
          Exception: Dummy error repeated
        
        Important: The app must be scalable.
        """ * 2,
        "project_context": "Long context stress test",
        "constraints": "Must sanitize noise and keep signal-to-noise > 0.5"
    }
]

# Combine with base scenarios for full 8-scenario suite
def get_full_scenarios():
    from benchmarks.benchmark_suite import BENCHMARK_SCENARIOS
    return BENCHMARK_SCENARIOS + EXTENDED_BENCHMARKS
