import asyncio
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from phase_3_workflow_job_matching.greenhouse_scraper.config import DEFAULT_JOB_FILTER
from phase_3_workflow_job_matching.src.embeddings.greenhouse_job_embedder import main as run_embedder

def main():
    print("Greenhouse Job Embedding Runner")
    print("==================================================")
    
    # Get cycle input
    default_cycle = DEFAULT_JOB_FILTER.get('cycle', 0)
    print(f"\nDefault Cycle Number: {default_cycle}")
    cycle_input = input(f"Enter Cycle Number (default {default_cycle}): ").strip()
    
    try:
        cycle = float(cycle_input) if cycle_input else default_cycle
        if cycle.is_integer():
             cycle = int(cycle)
    except ValueError:
        print(f"Invalid input. Using default cycle: {default_cycle}")
        cycle = default_cycle
        
    print(f"\nStarting embedding process for Cycle: {cycle}")
    print("--------------------------------------------------")
    
    # Run the embedder
    asyncio.run(run_embedder(cycle=cycle))

if __name__ == "__main__":
    main()
