import argparse
import logging
import json
import sys
from pathlib import Path

# Ensure the scm package directory is in the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from scm.graph.composer import SCMGraphComposer
from scm.agents.orchestrator import SCMAgentOrchestrator

def main():
    parser = argparse.ArgumentParser(description="SCM Agent Simulation Control")
    parser.add_argument(
        "node_dir", 
        type=str, 
        help="Path to the directory containing SCM node JSON files.",
        nargs='?', # Make node_dir optional
        default="scm/nodes" # Default relative to project root
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level). Includes agent observations."
    )
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="Only perform graph structure evaluation, do not execute."
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    # Resolve node directory path relative to the project root
    nodes_path = Path(args.node_dir)
    if not nodes_path.is_absolute():
        nodes_path = project_root / nodes_path
        
    logger.info(f"Using node directory: {nodes_path}")
    
    composer = SCMGraphComposer(str(nodes_path))
    
    logger.info("--- Initializing Composer & Agent ---")
    
    # Load, build DAG, generate plan first
    if not composer.load_nodes():
        logger.error("Failed to load nodes. Exiting.")
        sys.exit(1)
    if not composer.build_dag():
        logger.error("Failed to build DAG. Exiting.")
        sys.exit(1)
    if not composer.generate_execution_plan():
        logger.error("Failed to generate execution plan. Exiting.")
        sys.exit(1)
        
    # Initialize Agent
    try:
        agent = SCMAgentOrchestrator(composer)
    except ValueError as e:
         logger.error(f"Failed to initialize agent: {e}")
         sys.exit(1)
    
    # 1. Evaluate Graph Structure
    evaluation = agent.evaluate_graph_structure()
    logger.info("--- Graph Evaluation Summary by Agent ---")
    print(json.dumps(evaluation, indent=2))
    
    if args.evaluate_only:
        logger.info("Evaluation complete (--evaluate-only specified). Exiting.")
        sys.exit(0)
        
    # 2. Execute with Agent Control
    execution_completed = agent.execute_graph_with_agent_control()
    
    # 3. Get Final Results (from composer)
    logger.info("--- Final Graph Results (if execution completed/not halted early) ---")
    final_results = composer.get_final_results()
    print(json.dumps(final_results, indent=2))
    
    # 4. Suggest Optimizations (Stub)
    suggestions = agent.suggest_optimizations()
    logger.info("--- Agent Optimization Suggestions ---")
    for suggestion in suggestions:
        print(f"- {suggestion}")
        
    # 5. Review Agent Log (optional: show only in verbose?)
    if args.verbose:
        logger.info("--- Full Agent Decision Log ---")
        for entry in agent.get_agent_log():
            print(entry)
            
    if execution_completed:
        logger.info("Agent-controlled execution simulation finished successfully.")
        sys.exit(0)
    else:
        logger.warning("Agent-controlled execution simulation failed or was halted.")
        sys.exit(1)

if __name__ == "__main__":
    main() 