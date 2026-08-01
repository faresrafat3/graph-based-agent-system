"""
LLM Integration - Direct access to LLM providers (OpenAI, Anthropic, Stepfun, with Mock/Dry-Run Support)
"""

import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_llm(provider="stepfun", model=None, temperature=0):
    """
    Get LLM instance
    
    Args:
        provider: "stepfun", "openai", or "anthropic"
        model: Model name (defaults to STEPFUN_MODEL env or step-3.7-flash)
        temperature: Temperature for generation
    
    Returns:
        LLM instance
    """
    
    if provider == "stepfun":
        api_key = os.getenv("STEPFUN_API_KEY")
        base_url = os.getenv("STEPFUN_BASE_URL", "https://api.stepfun.ai/step_plan/v1")
        env_model = os.getenv("STEPFUN_MODEL", "step-3.7-flash")
        
        if not api_key:
            raise ValueError("STEPFUN_API_KEY not found in environment variables")
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError("langchain-openai is not installed. Please run pip install langchain-openai")
        
        target_model = model if (model and model not in ["gpt-4", "gpt-4o"]) else env_model
        return ChatOpenAI(
            model=target_model,
            temperature=temperature,
            api_key=api_key,
            base_url=base_url
        )
        
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError("langchain-openai is not installed. Please run pip install langchain-openai")
        
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=api_key
        )
    
    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError("langchain-anthropic is not installed. Please run pip install langchain-anthropic")
        
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            api_key=api_key
        )
    
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'stepfun', 'openai', or 'anthropic'")


def call_llm(prompt: str, system_prompt: str = "", provider="stepfun", model="step-1-8k", allow_mock: bool = True) -> str:
    """
    Call LLM directly. Fallback to structured Mock/Dry-Run response if API key is missing.
    
    Args:
        prompt: User prompt
        system_prompt: System prompt (optional)
        provider: LLM provider ("stepfun", "openai", "anthropic")
        model: Model name
        allow_mock: Allow dry-run fallback if no API keys exist
    
    Returns:
        LLM response as string
    """
    
    stepfun_key = os.getenv("STEPFUN_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    def has_stepfun():
        if not stepfun_key or len(stepfun_key) < 10:
            return False
        try:
            import langchain_openai
            return True
        except ImportError:
            return False

    def has_openai():
        if not openai_key or not openai_key.startswith("sk-"):
            return False
        try:
            import langchain_openai
            return True
        except ImportError:
            return False

    def has_anthropic():
        if not anthropic_key or not anthropic_key.startswith("sk-ant-"):
            return False
        try:
            import langchain_anthropic
            return True
        except ImportError:
            return False

    if not has_stepfun() and not has_openai() and not has_anthropic() and allow_mock:
        # Dry-run / Mock fallback for offline testing
        mock_response = {
            "tasks": [
                {
                    "id": "task_1",
                    "title": "Design System Architecture",
                    "description": "Create architectural diagram and define component boundaries",
                    "type": "architecture",
                    "priority": "high",
                    "dependencies": [],
                    "estimated_effort": "medium",
                    "assigned_system": "architect",
                    "acceptance_criteria": ["Architecture document created", "Component interfaces defined"]
                },
                {
                    "id": "task_2",
                    "title": "Implement Feature Core",
                    "description": "Implement essential feature logic based on architecture",
                    "type": "feature",
                    "priority": "high",
                    "dependencies": ["task_1"],
                    "estimated_effort": "large",
                    "assigned_system": "developer",
                    "acceptance_criteria": ["Feature logic working", "Unit tests passing"]
                },
                {
                    "id": "task_3",
                    "title": "Run Quality & Integration Tests",
                    "description": "Execute full test suite and verify test coverage",
                    "type": "testing",
                    "priority": "medium",
                    "dependencies": ["task_2"],
                    "estimated_effort": "medium",
                    "assigned_system": "tester",
                    "acceptance_criteria": ["Integration tests passing", "Coverage >= 80%"]
                }
            ],
            "metadata": {
                "total_tasks": 3,
                "high_priority": 2,
                "medium_priority": 1,
                "low_priority": 0,
                "estimated_total_effort": "large"
            },
            "clarifications_needed": []
        }
        return json.dumps(mock_response)
    
    # Select active provider dynamically if default requested but not configured
    active_provider = provider
    active_model = model

    if provider == "stepfun" and not has_stepfun():
        if has_openai():
            active_provider = "openai"
            active_model = "gpt-4"
        elif has_anthropic():
            active_provider = "anthropic"
            active_model = "claude-3-5-sonnet-20240620"

    # Get LLM instance
    llm = get_llm(provider=active_provider, model=active_model)
    from langchain_core.messages import HumanMessage, SystemMessage
    
    # Build messages
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))
    
    # Call LLM
    response = llm.invoke(messages)
    
    return response.content


# Test function
def test_llm():
    """Test LLM integration"""
    
    print("Testing LLM integration...")
    
    try:
        response = call_llm(
            prompt="Say 'Hello from LangChain!'",
            system_prompt="You are a helpful assistant.",
            allow_mock=True
        )
        print(f"✓ LLM response: {response[:100]}...")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


if __name__ == "__main__":
    test_llm()
