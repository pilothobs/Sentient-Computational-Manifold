import logging
import random
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# Use absolute imports
from scm.graph.composer import SCMGraphComposer
from scm.runtime.engine import SCMExecutionEngine
from scm.runtime.utils import load_json_file
from scm.monitoring.tracer import log_trace_event, get_tracer
from scm.adaptive.adaptation_manager import AdaptationManager

logger = logging.getLogger(__name__)

# --- Simulation Constants (adjust as needed) ---
CONFIDENCE_THRESHOLD_LOW = 0.7  # Below this, agent might intervene
ADAPTATION_TRIGGER_PROBABILITY = 0.1 # Chance an adaptation strategy might trigger
SECURITY_RISK_THRESHOLD = 2 # Example: More than 2 public nodes might be a risk

class SCMAgentOrchestrator:
    """Orchestrates SCM graph execution with intelligent agent oversight."""

    def __init__(self, composer: SCMGraphComposer, adaptation_log_path: Optional[str] = None):
        """Initialize the agent with a pre-loaded composer and adaptation log path."""
        self.composer = composer
        if not composer.execution_plan:
            raise ValueError("Composer must have a generated execution plan before agent initialization.")
        self.agent_log: List[str] = [] # Log of agent decisions and observations
        self.graph_evaluation: Dict[str, Any] = {}
        self.halt_execution = False # Flag to stop execution based on agent decision
        # Get tracer instance for logging agent-specific events
        self.tracer = get_tracer()
        # Initialize Adaptation Manager
        # Ensure absolute path is passed to AdaptationManager
        nodes_dir_abs = str(composer.node_folder_path.resolve()) 
        adapt_log = adaptation_log_path or f"{self.tracer.output_dir if self.tracer else '.'}/adaptation_log.jsonl"
        self.adaptation_manager = AdaptationManager(nodes_dir_abs, adapt_log)

    def _log_decision(self, message: str, data: Optional[Dict[str, Any]] = None, node_id: Optional[str] = None):
        """Logs an agent decision/observation and sends to tracer."""
        logger.info(f"[AGENT DECISION] {message}")
        self.agent_log.append(f"[DECISION] {message}")
        if self.tracer:
             trace_data = {"message": message}
             if data: trace_data.update(data)
             self.tracer.log_event("AGENT_DECISION", trace_data, node_id=node_id)

    def _log_observation(self, message: str, data: Optional[Dict[str, Any]] = None, node_id: Optional[str] = None):
        """Logs an agent observation and sends to tracer."""
        logger.debug(f"[AGENT OBSERVATION] {message}")
        self.agent_log.append(f"[OBSERVATION] {message}")
        if self.tracer:
             trace_data = {"message": message}
             if data: trace_data.update(data)
             self.tracer.log_event("AGENT_OBSERVATION", trace_data, node_id=node_id)

    def evaluate_graph_structure(self) -> Dict[str, Any]:
        """Evaluates the static graph structure for potential risks and characteristics."""
        logger.info("--- Agent Evaluating Graph Structure ---")
        log_trace_event("AGENT_EVAL_START", {})
        self.graph_evaluation = {}
        self.agent_log = [] # Reset log for new evaluation

        num_nodes = len(self.composer.nodes)
        self.graph_evaluation["node_count"] = num_nodes
        self._log_observation(f"Graph contains {num_nodes} nodes.", {"count": num_nodes})

        # Check for potential security risks (e.g., public nodes)
        public_nodes = [nid for nid, data in self.composer.nodes.items() 
                        if data.get("security_policy", {}).get("access_level") == "Public"]
        self.graph_evaluation["public_node_count"] = len(public_nodes)
        if len(public_nodes) > SECURITY_RISK_THRESHOLD:
            self._log_decision(f"High number ({len(public_nodes)}) of Public nodes detected: {public_nodes}. Potential security review needed.", 
                             {"count": len(public_nodes), "nodes": public_nodes, "risk_level": "High"})
            self.graph_evaluation["security_risk_level"] = "High"
        elif len(public_nodes) > 0:
             self._log_observation(f"{len(public_nodes)} Public nodes detected: {public_nodes}.",
                                {"count": len(public_nodes), "nodes": public_nodes, "risk_level": "Medium"})
             self.graph_evaluation["security_risk_level"] = "Medium"
        else:
            self.graph_evaluation["security_risk_level"] = "Low"

        # Check for statefulness
        stateful_nodes = [nid for nid, data in self.composer.nodes.items() 
                          if data.get("state_management", {}).get("type") in ["Stateful", "Contextual"]]
        self.graph_evaluation["stateful_node_count"] = len(stateful_nodes)
        if stateful_nodes:
            self._log_observation(f"{len(stateful_nodes)} stateful/contextual nodes detected: {stateful_nodes}.",
                                {"count": len(stateful_nodes), "nodes": stateful_nodes})

        # Check for resilience policies (e.g., presence of Fallbacks)
        fallback_policies = []
        for nid, data in self.composer.nodes.items():
            for policy in data.get("resilience_policy", []):
                if policy.get("action") == "Fallback":
                    fallback_policies.append((nid, policy.get("action_params", {}).get("node_ref")))
        self.graph_evaluation["fallback_policy_count"] = len(fallback_policies)
        if fallback_policies:
             self._log_observation(f"{len(fallback_policies)} Fallback resilience policies detected.", 
                                {"count": len(fallback_policies), "details": fallback_policies})

        # Check for adaptation strategies
        adaptation_nodes = [nid for nid, data in self.composer.nodes.items() if "adaptation_strategy" in data]
        self.graph_evaluation["adaptation_nodes_count"] = len(adaptation_nodes)
        if adaptation_nodes:
            self._log_observation(f"{len(adaptation_nodes)} nodes with adaptation strategies: {adaptation_nodes}",
                                {"count": len(adaptation_nodes), "nodes": adaptation_nodes})

        # Add more structural checks here (e.g., graph depth, width, common patterns)

        logger.info("--- Graph Structure Evaluation Complete ---")
        log_trace_event("AGENT_EVAL_END", {"evaluation_summary": self.graph_evaluation})
        return self.graph_evaluation

    def execute_graph_with_agent_control(self) -> bool:
        """Executes the graph simulation, allowing the agent to intervene and adapt."""
        self.tracer = get_tracer()
        if not self.tracer: return False # Error already logged by get_tracer
        if not self.composer.execution_plan: return False
        if not self.graph_evaluation: self.evaluate_graph_structure()

        logger.info("--- Starting Graph Execution with Agent Control & Adaptation ---")
        graph_info = {"plan_length": len(self.composer.execution_plan), "plan": self.composer.execution_plan}
        self.tracer.start_trace(graph_info)
        self.composer.execution_results = {}
        self.composer.execution_metadata = {}
        self.halt_execution = False
        
        intermediate_outputs: Dict[str, Dict[str, Any]] = {}
        overall_success = True
        adapted_nodes_this_run: Dict[str, str] = {} # original_id -> new_id

        # --- Use a copy of the plan in case adaptation modifies the node list for future runs --- 
        current_execution_plan = list(self.composer.execution_plan)

        for i, node_id in enumerate(current_execution_plan):
            # Check if this node was replaced by an adapted version earlier in this run
            if node_id in adapted_nodes_this_run:
                 actual_node_id = adapted_nodes_this_run[node_id]
                 self._log_observation(f"Node {node_id} was adapted earlier in this run. Using new version: {actual_node_id}", node_id=actual_node_id)
                 # Need to ensure the composer has loaded the new node if we were to re-run?
                 # For now, we just use the new ID for logging/lookup if needed later.
            else:
                 actual_node_id = node_id

            if self.halt_execution:
                self._log_decision(f"Execution halted by agent before node {actual_node_id}.", {"reason": "Agent decision"}, node_id=actual_node_id)
                log_trace_event("EXECUTION_HALTED", {"reason": "Agent decision", "halt_node": actual_node_id})
                overall_success = False
                break

            logger.info(f"[Agent Step {i+1}/{len(current_execution_plan)}] Considering node: {actual_node_id} (Original: {node_id})")
            log_trace_event("AGENT_STEP_START", {"step": i+1, "total_steps": len(current_execution_plan)}, actual_node_id)
            
            # --- Get Node Data --- 
            # Load data for the *actual* node being executed
            # This requires loading the adapted node if it exists
            node_data = None
            node_path = self.composer.node_paths.get(actual_node_id)
            if not node_path:
                 # Try constructing path based on ID if it was adapted
                 constructed_path = self.composer.node_folder_path / f"{actual_node_id}.json"
                 if constructed_path.exists():
                      node_path = constructed_path
                 else:
                      logger.error(f"Could not find node file for {actual_node_id}. Halting.")
                      self._log_decision(f"Node file not found for {actual_node_id}. Halting graph.", {"reason": "Node file missing"}, node_id=actual_node_id)
                      overall_success = False
                      break
                      
            try:
                 # Use utils loader which might be cached later
                 node_data = load_json_file(node_path) 
                 # Ensure composer's node cache is updated if needed? Or just use loaded data.
            except Exception as e:
                 logger.error(f"Failed to load node data for {actual_node_id} from {node_path}: {e}. Halting.")
                 self._log_decision(f"Failed to load node data for {actual_node_id}. Halting graph.", {"reason": "Node load error"}, node_id=actual_node_id)
                 overall_success = False
                 break
                 
            # --- Agent Pre-execution Checks --- 
            self.agent_pre_execution_check(actual_node_id, node_data, intermediate_outputs)
            if self.halt_execution:
                 self._log_decision(f"Execution halted by agent during pre-check for node {actual_node_id}.", {"reason": "Agent pre-check decision"}, node_id=actual_node_id)
                 log_trace_event("EXECUTION_HALTED", {"reason": "Agent pre-check decision", "node_id": actual_node_id})
                 overall_success = False
                 break

            # --- Execute Node --- 
            logger.info(f"Agent approves execution for node: {actual_node_id}")
            log_trace_event("AGENT_APPROVAL", {"action": "EXECUTE"}, actual_node_id)
            engine = SCMExecutionEngine(str(node_path))
            if engine.load_and_validate_node(): 
                if engine.execute(external_inputs=intermediate_outputs.get(actual_node_id)):
                    node_result = engine.get_result()
                    node_metadata = engine.get_metadata()
                    # Store results against the *original* node ID for consistent graph flow? Or actual?
                    # Let's use actual_node_id for results and metadata for now.
                    self.composer.execution_results[actual_node_id] = node_result
                    self.composer.execution_metadata[actual_node_id] = node_metadata
                    intermediate_outputs[actual_node_id] = node_result
                    logger.info(f"Node {actual_node_id} finished successfully.")
                    
                    # --- Agent Post-execution Checks & Adaptation --- 
                    self.agent_post_execution_check(actual_node_id, node_data, node_result, node_metadata)
                    if self.halt_execution:
                        self._log_decision(f"Execution halted by agent after node {actual_node_id} completed.", {"reason": "Agent post-check decision"}, node_id=actual_node_id)
                        log_trace_event("EXECUTION_HALTED", {"reason": "Agent post-check decision", "node_id": actual_node_id})
                        break
                        
                    # --- Call Adaptation Manager --- 
                    try:
                        # Pass the absolute node_path directly
                        newly_adapted_node_id = self.adaptation_manager.evaluate_and_adapt(node_path, node_data, node_metadata)
                        if newly_adapted_node_id:
                            self._log_observation(f"Node {actual_node_id} was adapted to {newly_adapted_node_id}.", {"original_id": actual_node_id, "new_id": newly_adapted_node_id}, node_id=actual_node_id)
                            adapted_nodes_this_run[actual_node_id] = newly_adapted_node_id
                    except Exception as adapt_e:
                         logger.error(f"Error during adaptation check for node {actual_node_id}: {adapt_e}", exc_info=True)
                         log_trace_event("ADAPTATION_ERROR", {"error": str(adapt_e)}, actual_node_id)

                else: # Node execution failed
                    logger.error(f"Execution failed for node: {actual_node_id}")
                    self._log_decision(f"Node {actual_node_id} failed execution. Halting graph.", {"error": engine.get_result()}, node_id=actual_node_id)
                    self.composer.execution_results[actual_node_id] = engine.get_result()
                    self.composer.execution_metadata[actual_node_id] = engine.get_metadata()
                    overall_success = False
                    break
            else: # Node loading failed
                 logger.error(f"Loading/validation failed for node: {actual_node_id}")
                 self._log_decision(f"Load/Validation failed for {actual_node_id}. Halting graph.", {"reason": "Load/Validation Failed"}, node_id=actual_node_id)
                 self.composer.execution_results[actual_node_id] = {"error": "Load/Validation failed"}
                 overall_success = False
                 break

        final_status = "HALTED" if self.halt_execution else ("SUCCESS" if overall_success else "FAILED")
        final_results_data = self.composer.get_final_results()
        self.tracer.end_trace(status=final_status, final_results=final_results_data)

        if final_status == "SUCCESS":
             logger.info("--- Graph Execution with Agent Control Completed Successfully ---")
        elif final_status == "HALTED":
             logger.warning("--- Graph Execution Halted by Agent --- ")
        else:
             logger.error("--- Graph Execution with Agent Control Failed --- ")
             
        return final_status == "SUCCESS" # Return True only if fully completed without halt or failure

    def agent_pre_execution_check(self, node_id: str, node_data: Dict[str, Any], current_outputs: Dict[str, Any]):
        """Agent logic evaluated before a node executes."""
        self._log_observation(f"Performing pre-execution checks for node {node_id}.", {"event": "PRE_CHECK_START"}, node_id=node_id)
        
        # Check security policy
        sec_policy = node_data.get("security_policy", {})
        access_level = sec_policy.get("access_level", "Internal")
        # Example: Agent might restrict execution of 'Private' nodes in certain contexts (not simulated here)
        if access_level == "Private":
             self._log_observation(f"Node {node_id} has access level: Private. Proceeding (simulation)...", {"access_level": access_level}, node_id=node_id)
             
        # Check state management requirements
        state_policy = node_data.get("state_management", {})
        if state_policy.get("type") in ["Stateful", "Contextual"]:
             mem_ref = state_policy.get("memory_ref")
             # Example: Agent checks if required memory store is available/healthy (not simulated here)
             self._log_observation(f"Node {node_id} requires state/context from {mem_ref}. Assuming available (simulation)...", {"state_type": state_policy.get("type"), "memory_ref": mem_ref}, node_id=node_id)
             
        # Simulate adaptation check
        if "adaptation_strategy" in node_data:
            if random.random() < ADAPTATION_TRIGGER_PROBABILITY:
                strat = node_data["adaptation_strategy"]
                decision_data = {"trigger": strat.get('trigger'), "method": strat.get('method')}
                self._log_decision(f"Adaptation strategy trigger simulated for node {node_id} (Trigger: {decision_data['trigger']}, Method: {decision_data['method']}). Halting execution for review/adaptation (simulation).", data=decision_data, node_id=node_id)
                self.halt_execution = True # Simulate halting for adaptation
        
        log_trace_event("AGENT_PRE_CHECK_END", {"halt_decision": self.halt_execution}, node_id)

    def agent_post_execution_check(self, node_id: str, node_data: Dict[str, Any], result: Dict[str, Any], metadata: Dict[str, Any]):
        """Agent logic evaluated after a node executes successfully."""
        self._log_observation(f"Performing post-execution checks for node {node_id}.", {"event": "POST_CHECK_START"}, node_id=node_id)

        # Check confidence score against threshold (if available)
        confidence = metadata.get("simulated_confidence")
        if confidence is not None:
            self._log_observation(f"Node {node_id} reported confidence: {confidence:.3f}", {"confidence": confidence}, node_id=node_id)
            if confidence < CONFIDENCE_THRESHOLD_LOW:
                decision_data = {"confidence": confidence, "threshold": CONFIDENCE_THRESHOLD_LOW}
                self._log_decision(f"Confidence ({confidence:.3f}) for node {node_id} is below threshold ({CONFIDENCE_THRESHOLD_LOW}).", data=decision_data, node_id=node_id)
                # Check resilience policy for fallback
                can_fallback = False
                for policy in node_data.get("resilience_policy", []):
                    # Basic condition check (in reality, this needs proper evaluation)
                    if "confidence" in policy.get("condition", "").lower() and policy.get("action") == "Fallback":
                         fallback_node = policy.get("action_params", {}).get("node_ref")
                         fallback_data = {"fallback_node": fallback_node, "condition": policy.get("condition")}
                         self._log_decision(f"Resilience policy allows Fallback to '{fallback_node}'. Suggesting fallback (simulation - not executing fallback path).", data=fallback_data, node_id=node_id)
                         # In a real agent, could trigger fallback path here
                         can_fallback = True
                         break
                if not can_fallback:
                     self._log_decision("No applicable Fallback policy found. Suggesting halt for human review.", {"reason": "Low confidence, no fallback"}, node_id=node_id)
                     self.halt_execution = True # Halt graph if confidence low and no fallback
                     
        # Check other resilience policies (Alert, etc.) - logging only for now
        for policy in node_data.get("resilience_policy", []):
            # Simulate condition being met (needs proper evaluation)
            if policy.get("action") == "Alert" and random.random() < 0.1: 
                alert_target = policy.get("action_params", {}).get("target_agent", "monitoring_system")
                alert_data = {"condition": policy.get("condition"), "alert_target": alert_target}
                self._log_observation(f"Simulating Resilience Alert trigger for node {node_id}: Condition '{alert_data['condition']}' met. Alert target: {alert_target}", data=alert_data, node_id=node_id)

        log_trace_event("AGENT_POST_CHECK_END", {"halt_decision": self.halt_execution}, node_id)

    def suggest_optimizations(self) -> List[str]:
        """(Stub) Suggests potential graph optimizations based on structure or simulated metrics."""
        # Get tracer if not already set
        if not hasattr(self, 'tracer') or not self.tracer:
             self.tracer = get_tracer()
             
        logger.info("--- Agent Analyzing for Optimizations (Stub) ---")
        log_trace_event("AGENT_OPTIMIZATION_START", {})
        suggestions = []
        
        # Example rule: If confidence consistently low for a node, suggest review/replacement
        low_confidence_nodes = []
        for node_id, meta in self.composer.execution_metadata.items():
             conf = meta.get("simulated_confidence")
             if conf is not None and conf < CONFIDENCE_THRESHOLD_LOW:
                 low_confidence_nodes.append(node_id)
        
        if len(low_confidence_nodes) > 1: # Example threshold
             suggestion = f"Multiple nodes ({low_confidence_nodes}) consistently show low confidence (<{CONFIDENCE_THRESHOLD_LOW}). Consider reviewing their models or resilience policies."
             suggestions.append(suggestion)
             self._log_observation(suggestion, {"type": "low_confidence", "nodes": low_confidence_nodes, "threshold": CONFIDENCE_THRESHOLD_LOW})
             
        # Example rule: Identify potential parallelization opportunities (nodes with no dependency between them)
        # More complex analysis needed here based on the DAG structure
        
        if not suggestions:
             suggestion = "No obvious optimization suggestions based on current simple rules and simulation data."
             suggestions.append(suggestion)
             self._log_observation(suggestion, {"type": "no_suggestions"})
             
        logger.info("--- Optimization Analysis Complete (Stub) ---")
        log_trace_event("AGENT_OPTIMIZATION_END", {"suggestions_count": len(suggestions), "suggestions": suggestions})
        return suggestions
        
    def get_agent_log(self) -> List[str]:
        return self.agent_log

# Example Usage (can be added to tools/agent_simulator.py)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Initialize tracer for direct execution
    initialize_tracer()
    
    # Assumes running from the project root (e.g., scm-env/)
    nodes_dir = "scm/nodes"
    composer = SCMGraphComposer(nodes_dir)
    
    logger.info("--- Initializing Composer & Agent ---")
    if composer.load_nodes() and composer.build_dag() and composer.generate_execution_plan():
        agent = SCMAgentOrchestrator(composer)
        
        # 1. Evaluate Graph Structure
        evaluation = agent.evaluate_graph_structure()
        logger.info("--- Graph Evaluation Summary ---")
        print(json.dumps(evaluation, indent=2))
        
        # 2. Execute with Agent Control
        agent.execute_graph_with_agent_control()
        
        # 3. Get Final Results (from composer)
        logger.info("--- Final Graph Results (if execution completed) ---")
        final_results = composer.get_final_results()
        print(json.dumps(final_results, indent=2))
        
        # 4. Suggest Optimizations (Stub)
        suggestions = agent.suggest_optimizations()
        logger.info("--- Agent Optimization Suggestions ---")
        for suggestion in suggestions:
            print(f"- {suggestion}")
            
        # 5. Review Agent Log
        logger.info("--- Full Agent Decision Log ---")
        for entry in agent.get_agent_log():
             print(entry)
    else:
        logger.error("Failed to initialize composer (load/build/plan). Cannot run agent.") 