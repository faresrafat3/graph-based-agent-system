"""
LLM Integration - Direct access to LLM providers (no Hermes)
"""

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_llm(provider="openai", model="gpt-4", temperature=0):
    """
    Get LLM instance
    
    Args:
        provider: "openai" or "anthropic"
        model: Model name
        temperature: Temperature for generation
    
    Returns:
        LLM instance
    """
    
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=api_key
        )
    
    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            api_key=api_key
        )
    
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'openai' or 'anthropic'")


def call_llm(prompt: str, system_prompt: str = "", provider="openai", model="gpt-4") -> str:
    """
    Call LLM directly (no Hermes)
    
    Args:
        prompt: User prompt
        system_prompt: System prompt (optional)
        provider: LLM provider
        model: Model name
    
    Returns:
        LLM response as string
    """
    
    # Get LLM instance
    llm = get_llm(provider=provider, model=model)
    
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
            provider="openai",
            model="gpt-4"
        )
        print(f"✓ LLM response: {response}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


if __name__ == "__main__":
    test_llm()
