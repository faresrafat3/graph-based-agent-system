"""
Software Builder - Main Entry Point
Runs the full Karpathy Pipeline: Context Curator → Task Decomposer → Deterministic Validator → Surgical Refiner
"""

import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the integrated Karpathy Pipeline
from agents.karpathy_pipeline import run_karpathy_pipeline


def main():
    """Main function - Executes the full Karpathy Engineering Pipeline"""
    
    print("=" * 80)
    print("  Software Builder - Karpathy Multi-Agent System")
    print("  Pipeline: Curate → Decompose → Validate → Refine")
    print("=" * 80)
    print()
    
    # Example requirements
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
    
    print("📥 Stage 1: Context Curator (Sanitizing Input)...")
    print("🤖 Stage 2: Task Decomposer (LLM Processing)...")
    print("🔍 Stage 3: Deterministic Validator (Zero-LLM Verification)...")
    print("🔧 Stage 4: Surgical Refiner (If Needed)...")
    print()
    
    result = run_karpathy_pipeline(
        requirements=requirements,
        project_context="Web application for small teams",
        constraints="Use modern tech stack, must be scalable"
    )
    
    print("=" * 80)
    print("  Pipeline Results")
    print("=" * 80)
    print()
    
    print(f"  Stage:              {result['stage']}")
    print(f"  Success:            {'✅' if result['success'] else '❌'} {result['success']}")
    print(f"  Quality Score:      {result.get('quality_score', 'N/A')}")
    print(f"  Signal-to-Noise:    {result.get('context_signal_to_noise', 'N/A')}")
    print(f"  Refinement Retries: {result.get('refinement_attempts', 0)}")
    print(f"  Total Tasks:        {len(result.get('tasks', []))}")
    print()
    
    tasks = result.get("tasks", [])
    if tasks:
        print("  Tasks:")
        print("  " + "-" * 76)
        for i, task in enumerate(tasks, 1):
            print(f"  {i}. {task.get('title', 'Untitled')}")
            print(f"     Type: {task.get('type', '-')}  |  Priority: {task.get('priority', '-')}  |  Effort: {task.get('estimated_effort', '-')}")
            print(f"     Assigned: {task.get('assigned_system', '-')}  |  Dependencies: {task.get('dependencies', [])}")
            print()
    
    violations = result.get("violations", [])
    if violations:
        print("  ⚠️  Violations:")
        print("  " + "-" * 76)
        for v in violations:
            print(f"  - {v}")
        print()
    
    print("=" * 80)


if __name__ == "__main__":
    main()
