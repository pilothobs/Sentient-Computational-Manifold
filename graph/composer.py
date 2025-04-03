import logging
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple, Set
from collections import defaultdict, deque

# Use absolute imports
from scm.runtime.engine import SCMExecutionEngine
from scm.runtime.utils import load_json_file, validate_node_data
# Import tracer helpers
from scm.monitoring.tracer import initialize_tracer, log_trace_event, get_tracer

logger = logging.getLogger(__name__)

class SCMGraphComposer:
    """Loads SCM nodes, builds a DAG, validates, and executes them in order."""

    def __init__(self, node_folder_path: str):
        self.node_folder_path = Path(node_folder_path)
        self.nodes: Dict[str, Dict[str, Any]] = {} # node_id -> node_data
        self.node_paths: Dict[str, Path] = {} # node_id -> file_path
        self.adj: Dict[str, List[str]] = defaultdict(list) # Adjacency list for DAG (node_id -> list of dependent node_ids)
        self.in_degree: Dict[str, int] = defaultdict(int)
        self.execution_plan: List[str] = []
        # Global trace ID is now managed by the tracer instance
        # self.global_trace_id: str | None = None 
        self.execution_results: Dict[str, Dict[str, Any]] = {}
        self.execution_metadata: Dict[str, Dict[str, Any]] = {}
        # Initialize the tracer (or rely on external initialization)
        # initialize_tracer() # Could do this here, or expect it from CLI

    def load_nodes(self) -> bool:
        """Loads all *.json node files from the specified folder."""
        logger.info(f"Loading nodes from folder: {self.node_folder_path}")
        if not self.node_folder_path.is_dir():
            logger.error(f"Node folder not found: {self.node_folder_path}")
            return False

        loaded_count = 0
        for file_path in self.node_folder_path.glob("*.json"):
            try:
                node_data = load_json_file(file_path)
                node_id = node_data.get("@id")
                if not node_id:
                    logger.warning(f"Skipping file {file_path.name}: Missing '@id' field.")
                    continue
                
                if node_id in self.nodes:
                     logger.warning(f"Duplicate node ID '{node_id}' found. Using file: {file_path.name}. Previous was: {self.node_paths[node_id].name}")
                     
                # Basic validation during load
                # Use schema from project root
                schema_path = Path(__file__).resolve().parent.parent / "schemas/scm_node.schema.json"
                if not validate_node_data(node_data, schema_path=schema_path):
                    logger.warning(f"Skipping invalid node file: {file_path.name}")
                    continue
                    
                self.nodes[node_id] = node_data
                self.node_paths[node_id] = file_path
                logger.debug(f"Successfully loaded node '{node_id}' from {file_path.name}")
                loaded_count += 1
            except Exception as e:
                logger.error(f"Failed to load or validate node from {file_path.name}: {e}")
        
        if loaded_count == 0:
             logger.error(f"No valid nodes loaded from {self.node_folder_path}")
             return False
             
        logger.info(f"Successfully loaded {loaded_count} valid nodes.")
        return True

    def build_dag(self) -> bool:
        """Builds the dependency graph (DAG) from loaded nodes."""
        logger.info("Building execution DAG...")
        all_node_ids = set(self.nodes.keys())
        self.adj.clear()
        self.in_degree = defaultdict(int, {node_id: 0 for node_id in all_node_ids})

        valid_dag = True
        for node_id, node_data in self.nodes.items():
            dependencies = node_data.get("depends_on", [])
            for dep in dependencies:
                dep_node_ref = dep.get("node_ref")
                if not dep_node_ref:
                    logger.error(f"Node '{node_id}' has a dependency with a missing 'node_ref'.")
                    valid_dag = False
                    continue
                
                if dep_node_ref not in all_node_ids:
                    logger.error(f"Node '{node_id}' depends on missing node '{dep_node_ref}'.")
                    valid_dag = False
                    continue
                
                # Add edge: dep_node_ref -> node_id
                self.adj[dep_node_ref].append(node_id)
                self.in_degree[node_id] += 1
                logger.debug(f"Added dependency: {dep_node_ref} -> {node_id}")

        if not valid_dag:
            logger.error("DAG validation failed due to missing nodes or references.")
            return False

        logger.info("DAG built successfully.")
        return True

    def generate_execution_plan(self) -> bool:
        """Generates a linear execution plan using topological sort."""
        logger.info("Generating execution plan using topological sort...")
        self.execution_plan = []
        # Use a copy of in_degree for the sort process
        current_in_degree = self.in_degree.copy()
        queue = deque([node_id for node_id in self.nodes if current_in_degree[node_id] == 0])
        processed_nodes = 0

        while queue:
            u = queue.popleft()
            self.execution_plan.append(u)
            processed_nodes += 1

            for v in self.adj[u]:
                current_in_degree[v] -= 1
                if current_in_degree[v] == 0:
                    queue.append(v)

        if processed_nodes != len(self.nodes):
            logger.error("Cycle detected in the graph! Cannot generate a linear execution plan.")
            # Identify nodes involved in the cycle (more complex logic needed)
            # Find nodes with in_degree > 0 after sort attempt
            cycle_nodes = [nid for nid, degree in current_in_degree.items() if degree > 0]
            logger.error(f"Nodes potentially involved in cycle: {cycle_nodes}")
            return False

        logger.info(f"Execution plan generated: {self.execution_plan}")
        return True

    def _check_trace_propagation(self) -> bool:
        """Checks if any node enables trace propagation."""
        for node_id in self.execution_plan:
             node_data = self.nodes[node_id]
             if node_data.get("observability", {}).get("trace_propagation", False):
                 logger.info(f"Trace propagation enabled by node '{node_id}'. Trace ID will be used if available.")
                 return True
        logger.info("Trace propagation not enabled by any node in the execution plan.")
        return False
        
    def execute_graph_simulation(self) -> bool:
        """Executes the graph node by node, passing outputs as inputs."""
        tracer = get_tracer()
        if not tracer: return False
        if not self.execution_plan: return False
        logger.info("--- Starting Graph Execution Simulation --- ")
        graph_info = {"plan_length": len(self.execution_plan), "plan": self.execution_plan}
        tracer.start_trace(graph_info)
        self.execution_results = {}
        self.execution_metadata = {}
        trace_enabled_by_nodes = self._check_trace_propagation()
        
        intermediate_outputs: Dict[str, Dict[str, Any]] = {} # Store outputs from completed nodes
        overall_success = True
        
        for i, node_id in enumerate(self.execution_plan):
            logger.info(f"[Step {i+1}/{len(self.execution_plan)}] Executing node: {node_id}")
            log_trace_event("COMPOSER_STEP_START", {"step": i+1, "total_steps": len(self.execution_plan)}, node_id)
            node_path = self.node_paths[node_id]
            node_data = self.nodes[node_id]
            engine = SCMExecutionEngine(str(node_path))

            # --- Prepare Inputs for Current Node --- 
            inputs_for_node: Dict[str, Any] = {}
            missing_inputs = False
            required_inputs = node_data.get("inputs", [])
            for req_input in required_inputs:
                input_name = req_input.get("input_name")
                source_node_id = req_input.get("source") # Should match a previous node ID
                
                if not input_name or not source_node_id:
                     logger.warning(f"Node '{node_id}' has invalid input definition: {req_input}. Skipping input.")
                     continue
                     
                # Check if source node executed and produced output
                if source_node_id in intermediate_outputs:
                    source_output_data = intermediate_outputs[source_node_id]
                    # Need to map source node's output_name to this node's input_name
                    # Assumption: The input_name directly matches an output_name from the source node
                    if input_name in source_output_data:
                         inputs_for_node[input_name] = source_output_data[input_name]
                         logger.debug(f"Passing output '{input_name}' from '{source_node_id}' to '{node_id}'")
                    else:
                         logger.error(f"Node '{node_id}' requires input '{input_name}', but source '{source_node_id}' did not produce it. Available outputs: {list(source_output_data.keys())}")
                         missing_inputs = True
                         break # Stop processing inputs for this node
                elif source_node_id != "external_parameter": # Only fail if source was another node
                     logger.error(f"Node '{node_id}' requires input '{input_name}' from source '{source_node_id}', but source has not executed or produced output.")
                     missing_inputs = True
                     break
                # If source is "external_parameter", engine will generate mock data if inputs_for_node remains empty
                
            if missing_inputs:
                 logger.error(f"Cannot execute node '{node_id}' due to missing inputs.")
                 log_trace_event("NODE_ERROR", {"error": "Missing required inputs from dependencies"}, node_id)
                 overall_success = False
                 break # Stop graph execution

            # Execute Node - Pass the collected inputs 
            if engine.load_and_validate_node():
                # Pass inputs_for_node only if it's not empty, otherwise let engine generate mocks
                external_inputs_arg = inputs_for_node if inputs_for_node else None
                if engine.execute(external_inputs=external_inputs_arg):
                    node_result = engine.get_result()
                    node_metadata = engine.get_metadata()
                    self.execution_results[node_id] = node_result
                    self.execution_metadata[node_id] = node_metadata
                    intermediate_outputs[node_id] = node_result # Store result for downstream nodes
                    logger.info(f"Node {node_id} finished successfully.")
                    log_trace_event("COMPOSER_STEP_END", {"status": "SUCCESS"}, node_id)
                else:
                    logger.error(f"Execution failed for node: {node_id}")
                    self.execution_results[node_id] = engine.get_result() # Store error result
                    self.execution_metadata[node_id] = engine.get_metadata()
                    log_trace_event("COMPOSER_STEP_END", {"status": "FAILED"}, node_id)
                    overall_success = False
                    break
            else:
                 logger.error(f"Loading/validation failed for node: {node_id}")
                 self.execution_results[node_id] = {"error": "Load/Validation failed"}
                 log_trace_event("COMPOSER_STEP_END", {"status": "LOAD_FAILED"}, node_id)
                 overall_success = False
                 break
                 
        final_status = "SUCCESS" if overall_success else "FAILED"
        final_results_data = self.get_final_results()
        tracer.end_trace(status=final_status, final_results=final_results_data)
        
        if overall_success:
             logger.info("--- Graph Execution Simulation Completed Successfully ---")
        else:
             logger.error("--- Graph Execution Simulation Failed --- ")
             
        return overall_success

    def get_final_results(self) -> Dict[str, Any]:
        """Returns the results from the terminal nodes of the graph."""
        final_results = {}
        # Ensure plan exists before iterating
        if not self.execution_plan: return final_results 
        for node_id in self.execution_plan:
            # A terminal node has no outgoing edges in our built adj list
            if node_id in self.nodes and not self.adj[node_id]: 
                final_results[node_id] = self.execution_results.get(node_id)
        return final_results
        
    def compose_and_execute(self) -> bool:
        """Helper method to run the full load, build, plan, execute sequence."""
        if not self.load_nodes():
            return False
        if not self.build_dag():
            return False
        if not self.generate_execution_plan():
            return False
        if not self.execute_graph_simulation():
            return False
        return True

# Example Usage (can be added to a separate script like tools/execute_graph.py)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Initialize tracer for direct execution
    initialize_tracer()
    
    # Assumes running from the project root (e.g., scm-env/)
    nodes_dir = "scm/nodes"
    composer = SCMGraphComposer(nodes_dir)
    
    logger.info("--- Initializing SCM Graph Composer ---")
    if composer.compose_and_execute():
        logger.info("--- Final Graph Results (Terminal Nodes) ---")
        final_results = composer.get_final_results()
        print(json.dumps(final_results, indent=2))
        
        logger.info("--- Full Execution Metadata --- ")
        # print(json.dumps(composer.execution_metadata, indent=2)) # Can be verbose
    else:
        logger.error("Graph composition or execution failed.")
        logger.info("--- Partial Execution Results ---")
        print(json.dumps(composer.execution_results, indent=2)) 