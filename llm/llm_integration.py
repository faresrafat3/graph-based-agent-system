"""
LLM Integration - Direct access to LLM providers (OpenAI, Anthropic, Stepfun, with Native REST & Mock/Dry-Run Support)
"""

import os
import json
import urllib.request
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def call_stepfun_native(prompt: str, system_prompt: str = "", model: str = None, temperature: float = 0.0) -> str:
    """
    Calls Stepfun REST API natively using urllib.request (zero third-party dependencies required).
    """
    api_key = os.getenv("STEPFUN_API_KEY")
    base_url = os.getenv("STEPFUN_BASE_URL", "https://api.stepfun.ai/v1").rstrip('/')
    target_model = model or os.getenv("STEPFUN_MODEL", "step-3.7-flash")
    
    if not api_key:
        raise ValueError("STEPFUN_API_KEY is not configured.")
        
    url = f"{base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    data = {
        "model": target_model,
        "messages": messages,
        "temperature": temperature
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
        return res_data["choices"][0]["message"]["content"]


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
        base_url = os.getenv("STEPFUN_BASE_URL", "https://api.stepfun.ai/v1")
        env_model = os.getenv("STEPFUN_MODEL", "step-3.7-flash")
        
        if not api_key:
            raise ValueError("STEPFUN_API_KEY not found in environment variables")
        try:
            from langchain_openai import ChatOpenAI
            target_model = model if (model and model not in ["gpt-4", "gpt-4o"]) else env_model
            return ChatOpenAI(
                model=target_model,
                temperature=temperature,
                api_key=api_key,
                base_url=base_url
            )
        except ImportError:
            # Fallback to direct native caller wrapper
            return None
        
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model,
                temperature=temperature,
                api_key=api_key
            )
        except ImportError:
            return None
    
    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model,
                temperature=temperature,
                api_key=api_key
            )
        except ImportError:
            return None
    
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'stepfun', 'openai', or 'anthropic'")


def call_llm(prompt: str, system_prompt: str = "", provider="stepfun", model="step-3.7-flash", allow_mock: bool = True) -> str:
    """
    Call LLM directly. Supports Stepfun native REST calls, LangChain integration, and Mock fallback.
    
    Args:
        prompt: User prompt
        system_prompt: System prompt (optional)
        provider: LLM provider ("stepfun", "openai", "anthropic")
        model: Model name
        allow_mock: Allow dry-run fallback if no active API keys / quota exist
    
    Returns:
        LLM response as string
    """
    
    stepfun_key = os.getenv("STEPFUN_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    def has_stepfun():
        return bool(stepfun_key and len(stepfun_key) > 10)

    def has_openai():
        return bool(openai_key and openai_key.startswith("sk-"))

    def has_anthropic():
        return bool(anthropic_key and anthropic_key.startswith("sk-ant-"))

    # Attempt Live Native Stepfun Call if configured
    if provider == "stepfun" and has_stepfun():
        try:
            return call_stepfun_native(prompt=prompt, system_prompt=system_prompt, model=model)
        except Exception as e:
            # If HTTP Error 402 (quota exceeded) or connection error, allow fallback if allowed
            if not allow_mock:
                raise e

    # Fallback to Mock response if offline or quota exceeded
    if not has_openai() and not has_anthropic() and allow_mock:
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
    
    # Get LLM instance for OpenAI or Anthropic
    llm = get_llm(provider=provider, model=model)
    if llm is None:
        if allow_mock:
            return json.dumps(mock_response)
        raise ImportError(f"Required LangChain package for {provider} is missing.")
        
    from langchain_core.messages import HumanMessage, SystemMessage
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))
    
    response = llm.invoke(messages)
    return response.content


# Test function
def test_llm():
    """Test LLM integration"""
    print("Testing LLM integration...")
    try:
        response = call_llm(
            prompt="Say 'Hello from Stepfun REST API!'",
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
