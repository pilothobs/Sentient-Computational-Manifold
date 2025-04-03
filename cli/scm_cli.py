import argparse
import logging
import json
import sys
from pathlib import Path

# Ensure the scm package directory is in the Python path
# This allows importing sibling modules (graph, runtime, agents)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root.parent)) # Add scm-env/ to path

# Use absolute imports from the scm package root
from scm.runtime.utils import load_json_file, validate_node_data
from scm.runtime.engine import SCMExecutionEngine
from scm.graph.composer import SCMGraphComposer
from scm.agents.orchestrator import SCMAgentOrchestrator
from scm.monitoring.tracer import initialize_tracer, get_tracer # Added get_tracer

# --- Logging Setup ---
logger = logging.getLogger("scm_cli")

def configure_logging(verbose: bool):
    log_level = logging.DEBUG if verbose else logging.INFO
    # Configure root logger for simplicity, adjust if more complex handlers are needed
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)] # Ensure logs go to stdout
    )
    # Suppress overly verbose logs from dependencies if needed
    # logging.getLogger("some_dependency").setLevel(logging.WARNING)
    logger.info(f"Logging level set to: {logging.getLevelName(log_level)}")

# --- Command Functions ---

def handle_validate(args):
    """Handles the 'validate' command."""
    logger.info(f"Validating node file: {args.node_path}")
    node_path = Path(args.node_path)
    if not node_path.exists():
        logger.error(f"Node file not found: {node_path}")
        return False
    if not node_path.is_file():
         logger.error(f"Path provided is not a file: {node_path}")
         return False

    try:
        node_data = load_json_file(node_path)
        schema_path = Path(__file__).resolve().parent.parent / "schemas/scm_node.schema.json"
        if validate_node_data(node_data, schema_path=schema_path):
            print(f"\n✅ Node '{node_path.name}' is valid according to the schema.")
            return True
        else:
            print(f"\n❌ Node '{node_path.name}' failed validation.")
            return False
    except Exception as e:
        logger.error(f"An error occurred during validation: {e}", exc_info=args.verbose)
        return False

def handle_compose(args):
    """Handles the 'compose' command."""
    logger.info(f"Composing graph from directory: {args.nodes_dir}")
    nodes_path = Path(args.nodes_dir)
    composer = SCMGraphComposer(str(nodes_path))

    if not composer.load_nodes(): return False
    if not composer.build_dag(): return False
    if not composer.generate_execution_plan(): return False

    print("\n--- Graph Composition Summary ---")
    print(f"Nodes loaded: {len(composer.nodes)}")
    print("Execution Plan (Topological Order):")
    for i, node_id in enumerate(composer.execution_plan):
        purpose = composer.nodes[node_id].get('purpose_statement', 'N/A')
        print(f"  {i+1}. {node_id} - Purpose: {purpose[:60]}{'...' if len(purpose)>60 else ''}")
        
    # You could add checks here for cycles or disconnected components if needed
    return True

def handle_simulate(args):
    """Handles the 'simulate' command using the basic composer execution."""
    logger.info(f"Simulating graph execution from directory: {args.nodes_dir}")
    nodes_path = Path(args.nodes_dir)
    composer = SCMGraphComposer(str(nodes_path))
    
    # Use the composer's combined method
    success = composer.compose_and_execute()

    print("\n--- Simulation Results (Terminal Nodes) ---")
    final_results = composer.get_final_results()
    print(json.dumps(final_results, indent=2))

    if args.trace or args.verbose:
        print("\n--- Execution Metadata (Per Node) ---")
        print(json.dumps(composer.execution_metadata, indent=2))
        tracer = get_tracer() # Get tracer to print ID
        if tracer and tracer.session_id:
             print(f"Trace ID: {tracer.session_id}")
             print(f"Trace Log: {tracer.trace_file_path}")
             print(f"Trace Summary: {tracer.output_dir / f'summary_{tracer.session_id}.json'}")

    if success:
        print("\n✅ Graph simulation completed successfully.")
        return True
    else:
        print("\n❌ Graph simulation failed or was interrupted.")
        # Print partial results if available
        if composer.execution_results:
            print("\n--- Partial/Error Results ---")
            print(json.dumps(composer.execution_results, indent=2))
        return False

def handle_agent_run(args):
    """Handles the 'agent-run' command."""
    logger.info(f"Starting Agent-controlled execution simulation for directory: {args.nodes_dir}")
    nodes_path = Path(args.nodes_dir)
    composer = SCMGraphComposer(str(nodes_path))
    
    # Initialize composer first
    if not composer.load_nodes(): return False
    if not composer.build_dag(): return False
    if not composer.generate_execution_plan(): return False
    
    try:
        agent = SCMAgentOrchestrator(composer)
    except ValueError as e:
        logger.error(f"Failed to initialize agent: {e}")
        return False
        
    # Agent evaluates first (implicitly called if needed, but good practice)
    evaluation = agent.evaluate_graph_structure()
    print("\n--- Agent Graph Evaluation Summary ---")
    print(json.dumps(evaluation, indent=2))
    
    # Agent executes
    execution_completed = agent.execute_graph_with_agent_control()
    
    print("\n--- Final Graph Results (if execution completed/not halted) ---")
    final_results = composer.get_final_results() # Get results via composer
    print(json.dumps(final_results, indent=2))
    
    if args.trace or args.verbose:
        print("\n--- Execution Metadata (Per Node) ---")
        print(json.dumps(composer.execution_metadata, indent=2))
        # Get tracer to print ID and log file paths
        tracer = get_tracer()
        if tracer and tracer.session_id:
            print(f"Trace ID: {tracer.session_id}")
            print(f"Trace Log: {tracer.trace_file_path}")
            print(f"Trace Summary: {tracer.output_dir / f'summary_{tracer.session_id}.json'}")
        print("\n--- Agent Decision Log ---")
        for entry in agent.get_agent_log():
            print(entry)

    if execution_completed:
        print("\n✅ Agent-controlled execution simulation finished successfully.")
        return True
    else:
        print("\n⚠️ Agent-controlled execution simulation failed or was halted by the agent.")
        # Print partial results if available
        if composer.execution_results:
            print("\n--- Partial/Error Results ---")
            print(json.dumps(composer.execution_results, indent=2))
        return False

def handle_evaluate(args):
    """Handles the 'evaluate' command (agent evaluation only)."""
    logger.info(f"Evaluating graph structure with agent for directory: {args.nodes_dir}")
    nodes_path = Path(args.nodes_dir)
    composer = SCMGraphComposer(str(nodes_path))

    # Initialize composer first
    if not composer.load_nodes(): return False
    if not composer.build_dag(): return False
    if not composer.generate_execution_plan(): return False
    
    try:
        agent = SCMAgentOrchestrator(composer)
    except ValueError as e:
        logger.error(f"Failed to initialize agent: {e}")
        return False

    # Agent evaluates
    evaluation = agent.evaluate_graph_structure()
    print("\n--- Agent Graph Evaluation Summary ---")
    print(json.dumps(evaluation, indent=2))
    
    # Optionally show agent log for evaluation phase
    if args.verbose:
        # Get tracer to print ID and log file paths if initialized
        tracer = get_tracer()
        if tracer and tracer.session_id:
             print(f"\nTrace ID (for evaluation events): {tracer.session_id}")
             print(f"Trace Log: {tracer.trace_file_path}")
        print("\n--- Agent Evaluation Log ---")
        for entry in agent.get_agent_log():
            print(entry)
            
    print("\n✅ Graph evaluation completed.")
    return True

# --- Main CLI Parsing and Execution ---

def main():
    parser = argparse.ArgumentParser(
        description="Sentient Computational Manifold (SCM) Command Line Interface",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose (DEBUG level) logging.")
    # Add --trace later if needed, often covered by verbose for now
    # parser.add_argument("--trace", action="store_true", help="Display trace propagation information.")
    parser.add_argument("--trace-dir", type=str, default="./scm_traces", help="Directory to store trace files (default: ./scm_traces).")
    
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # --- Validate Command ---
    parser_validate = subparsers.add_parser("validate", help="Validate a single SCM node file against the schema.")
    parser_validate.add_argument("node_path", type=str, help="Path to the SCM node JSON file.")
    parser_validate.set_defaults(func=handle_validate)

    # --- Compose Command ---
    parser_compose = subparsers.add_parser("compose", help="Load nodes, build the DAG, and show the execution plan.")
    parser_compose.add_argument("nodes_dir", type=str, nargs='?', default="scm/nodes", help="Directory containing SCM node JSON files (default: scm/nodes).")
    parser_compose.set_defaults(func=handle_compose)

    # --- Simulate Command ---
    parser_simulate = subparsers.add_parser("simulate", help="Compose and execute the graph simulation using the basic engine.")
    parser_simulate.add_argument("nodes_dir", type=str, nargs='?', default="scm/nodes", help="Directory containing SCM node JSON files (default: scm/nodes).")
    parser_simulate.add_argument("--trace", action="store_true", help="Show execution metadata and trace file info.")
    parser_simulate.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output (redundant if set globally, but needed for parser). Set globally for logging.")
    parser_simulate.set_defaults(func=handle_simulate)

    # --- Agent-Run Command ---
    parser_agent_run = subparsers.add_parser("agent-run", help="Compose and execute the graph simulation under agent control.")
    parser_agent_run.add_argument("nodes_dir", type=str, nargs='?', default="scm/nodes", help="Directory containing SCM node JSON files (default: scm/nodes).")
    parser_agent_run.add_argument("--trace", action="store_true", help="Show execution metadata, trace file info, and agent log.")
    parser_agent_run.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output (redundant if set globally, but needed for parser). Set globally for logging.")
    parser_agent_run.set_defaults(func=handle_agent_run)

    # --- Evaluate Command ---
    parser_evaluate = subparsers.add_parser("evaluate", help="Use the agent to evaluate the graph structure without executing.")
    parser_evaluate.add_argument("nodes_dir", type=str, nargs='?', default="scm/nodes", help="Directory containing SCM node JSON files (default: scm/nodes).")
    parser_evaluate.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output (redundant if set globally, but needed for parser). Set globally for logging.")
    parser_evaluate.set_defaults(func=handle_evaluate)
    
    # --- Parse Arguments ---
    args = parser.parse_args()
    
    # --- Configure Logging ---
    # Pass the global verbose flag to the logging setup
    configure_logging(args.verbose)
    
    # --- Initialize Tracer --- 
    # Initialize tracer early, using the specified or default directory
    # This makes it available globally via get_tracer()
    trace_output_dir = Path(args.trace_dir)
    if not trace_output_dir.is_absolute():
        script_dir = Path(__file__).resolve().parent # .../scm-env/scm/cli
        project_root_guess = script_dir.parent.parent # .../scm-env/
        trace_output_dir = project_root_guess / trace_output_dir
        logger.debug(f"Resolved relative trace dir '{args.trace_dir}' to '{trace_output_dir}'")
    initialize_tracer(output_dir=str(trace_output_dir))
    
    # --- Resolve Node Directory Path --- 
    # Make paths relative to project root if not absolute and command needs it
    if hasattr(args, 'nodes_dir') and args.nodes_dir:
        nodes_path = Path(args.nodes_dir)
        if not nodes_path.is_absolute():
            # Assume relative to the directory containing the `scm` folder (project root)
            script_dir = Path(__file__).parent # .../scm-env/scm/cli
            project_root_guess = script_dir.parent.parent # .../scm-env/
            resolved_path = project_root_guess / nodes_path
            logger.debug(f"Resolved relative path '{args.nodes_dir}' to '{resolved_path}'")
            args.nodes_dir = str(resolved_path)
        else:
             logger.debug(f"Using absolute path for nodes_dir: {args.nodes_dir}")
    elif hasattr(args, 'node_path') and args.node_path:
         node_file_path = Path(args.node_path)
         if not node_file_path.is_absolute():
            script_dir = Path(__file__).parent # .../scm-env/scm/cli
            project_root_guess = script_dir.parent.parent # .../scm-env/
            resolved_path = project_root_guess / node_file_path
            logger.debug(f"Resolved relative path '{args.node_path}' to '{resolved_path}'")
            args.node_path = str(resolved_path)
         else:
             logger.debug(f"Using absolute path for node_path: {args.node_path}")

    # --- Execute Command Function ---
    if hasattr(args, 'func'):
        success = args.func(args)
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main() 