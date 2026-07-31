"""
Software Builder - Main Entry Point
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import agents
from agents.task_decomposer import decompose_requirements


def main():
    """Main function"""
    
    print("=" * 80)
    print("Software Builder - Multi-Agent System")
    print("=" * 80)
    print()
    
    # Check API keys
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not openai_key and not anthropic_key:
        print("❌ Error: No API keys found!")
        print("Please set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env file")
        return
    
    print("✓ API keys found")
    print()
    
    # Example usage
    print("Example: Decomposing requirements...")
    print()
    
    requirements = """
    Build a task management application with the following features:
    - User authentication (login/register)
    - Create, read, update, delete tasks
    - Assign tasks to team members
    - Set task priorities (high/medium/low)
    - Add due dates to tasks
    - Send email notifications for task assignments and due dates
    - Generate reports on task completion rates
    """
    
    result = decompose_requirements(
        requirements=requirements,
        project_context="Web application for small teams",
        constraints="Use modern tech stack, must be scalable"
    )
    
    print("=" * 80)
    print("Results:")
    print("=" * 80)
    print()
    
    print(f"Success: {result['success']}")
    print(f"Total Tasks: {len(result['tasks'])}")
    print()
    
    if result['tasks']:
        print("Tasks:")
        print("-" * 80)
        for i, task in enumerate(result['tasks'], 1):
            print(f"{i}. {task.get('title')}")
            print(f"   Type: {task.get('type')}")
            print(f"   Priority: {task.get('priority')}")
            print(f"   Assigned to: {task.get('assigned_system')}")
            print(f"   Effort: {task.get('estimated_effort')}")
            print(f"   Dependencies: {task.get('dependencies', [])}")
            print()
    
    if result['clarifications_needed']:
        print("Clarifications Needed:")
        print("-" * 80)
        for clarification in result['clarifications_needed']:
            print(f"- {clarification}")
        print()
    
    print("=" * 80)


if __name__ == "__main__":
    main()
