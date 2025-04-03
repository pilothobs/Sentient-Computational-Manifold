import argparse
import logging
import json
import sys
from pathlib import Path

# Ensure the scm package directory is in the Python path
# This allows running the script from the root directory
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from scm.graph.composer import SCMGraphComposer

def main():
    parser = argparse.ArgumentParser(description="SCM Graph Execution Simulator")
    parser.add_argument(
        "node_dir", 
        type=str, 
        help="Path to the directory containing SCM node JSON files.",
        default="scm/nodes" # Default relative to project root
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level)."
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
    
    logger.info("--- Initializing SCM Graph Composer ---")
    if composer.compose_and_execute():
        logger.info("--- Final Graph Results (Terminal Nodes) ---")
        final_results = composer.get_final_results()
        print(json.dumps(final_results, indent=2))
        
        if args.verbose:
            logger.info("--- Full Execution Metadata --- ")
            print(json.dumps(composer.execution_metadata, indent=2))
            logger.info("--- Full Execution Results --- ")
            print(json.dumps(composer.execution_results, indent=2))
            
        logger.info("Graph execution simulation completed successfully.")
        sys.exit(0)
    else:
        logger.error("Graph composition or execution failed.")
        logger.info("--- Partial Execution Results ---")
        print(json.dumps(composer.execution_results, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main() 