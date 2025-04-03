import json
import logging
import copy
import random
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import semver # Using the 'semver' library (pip install semver)

# Use absolute imports
from scm.runtime.utils import load_json_file, validate_node_data

logger = logging.getLogger(__name__)

# --- Adaptation Constants ---
# Example: If confidence < this OR execution time > this, trigger Performance_Degradation
PERFORMANCE_CONFIDENCE_THRESHOLD = 0.75
PERFORMANCE_TIME_THRESHOLD_MS = 1000 # Example threshold (1 second)

class AdaptationManager:
    """Manages node adaptation based on triggers and defined strategies."""

    def __init__(self, nodes_dir: str, adaptation_log_path: str = "./adaptation_log.jsonl"):
        self.nodes_dir = Path(nodes_dir).resolve() # Resolve to absolute path on init
        self.adaptation_log_path = Path(adaptation_log_path)
        self.nodes_dir.mkdir(parents=True, exist_ok=True)
        # Ensure parent of log exists
        self.adaptation_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache of nodes? Could optimize if loading many times.
        # self.node_cache: Dict[str, Dict[str, Any]] = {}

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _log_adaptation_event(self, event_data: Dict[str, Any]):
        """Logs an adaptation event to the JSONL file."""
        event_data["log_timestamp"] = self._now()
        try:
            with open(self.adaptation_log_path, 'a') as f:
                json.dump(event_data, f)
                f.write('\n')
            logger.info(f"Adaptation event logged for node {event_data.get('original_node_id')}")
        except Exception as e:
            logger.error(f"Failed to log adaptation event: {e}")
            
    def _get_next_version(self, current_version_str: str) -> str:
        """Increments the minor version using semantic versioning."""
        try:
            # Use semver library (version 2.x or 3.x)
            ver = semver.VersionInfo.parse(current_version_str)
            next_ver = ver.bump_minor() # Bump minor for adaptation
            return str(next_ver)
        except ValueError:
            logger.warning(f"Could not parse version '{current_version_str}'. Defaulting to manual increment.")
            parts = current_version_str.split('.')
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                 return f"{parts[0]}.{int(parts[1]) + 1}.0"
            return f"{current_version_str}-adapted" # Fallback

    def check_adaptation_triggers(self, node_data: Dict[str, Any], metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Checks if any adaptation trigger condition is met."""
        if "adaptation_strategy" not in node_data:
            return None

        strategy = node_data["adaptation_strategy"]
        trigger = strategy.get("trigger")
        metric_ref = strategy.get("metric_ref") # Often linked to trigger condition
        
        # --- Evaluate Triggers --- 
        triggered_condition = None
        trigger_details = {}

        if trigger == "Performance_Degradation":
            confidence = metrics.get("simulated_confidence")
            exec_time = metrics.get("execution_duration_ms")
            
            if confidence is not None and confidence < PERFORMANCE_CONFIDENCE_THRESHOLD:
                 triggered_condition = "Low Confidence"
                 trigger_details = {"confidence": confidence, "threshold": PERFORMANCE_CONFIDENCE_THRESHOLD}
            elif exec_time is not None and exec_time > PERFORMANCE_TIME_THRESHOLD_MS:
                 triggered_condition = "High Execution Time"
                 trigger_details = {"execution_time_ms": exec_time, "threshold_ms": PERFORMANCE_TIME_THRESHOLD_MS}
            # Could also use metric_ref here if specified

        elif trigger == "External_Feedback":
            # Simulation: Randomly trigger based on probability
            if random.random() < 0.05: # 5% chance
                 triggered_condition = "Simulated External Feedback"
                 trigger_details = {"feedback_source": "simulated_monitor"}
                 
        elif trigger == "Scheduled_Review":
             # Simulation: Trigger if node hasn't been adapted recently (e.g., check timestamp)
             # This requires storing last adaptation time, perhaps in node metadata or separate DB.
             # For now, we'll simulate randomly.
             if random.random() < 0.02: # 2% chance per evaluation
                  triggered_condition = "Simulated Scheduled Review Due"
                  trigger_details = {"reason": "Simulated time elapsed"}
                  
        elif trigger == "Manual_Trigger":
             # This would typically be triggered by an external system/user
             # Not simulated here during automatic checks
             pass

        if triggered_condition:
             logger.info(f"Adaptation triggered for node {node_data['@id']}! Condition: {triggered_condition}")
             strategy["_trigger_condition"] = triggered_condition # Store why it triggered
             strategy["_trigger_details"] = trigger_details
             return strategy
             
        return None

    def perform_adaptation(self, node_data: Dict[str, Any], triggered_strategy: Dict[str, Any], adapting_agent_ref: str = "agent_adaptor_v1") -> Optional[str]:
        """Simulates adaptation, creates a new node version, and logs the event."""
        original_node_id = node_data["@id"]
        adaptation_method = triggered_strategy.get("method")
        method_params = triggered_strategy.get("method_params", {})
        trigger_condition = triggered_strategy.get("_trigger_condition", "Unknown")
        trigger_details = triggered_strategy.get("_trigger_details", {})

        logger.info(f"Performing adaptation for {original_node_id} using method: {adaptation_method}")

        # --- Simulate Adaptation Action --- 
        new_node_data = copy.deepcopy(node_data)
        adaptation_rationale = f"Adapted due to '{trigger_condition}'. Method: '{adaptation_method}'. Details: {trigger_details}."
        
        # Modify the *new* node data based on the method (simulation)
        if adaptation_method == "Retrain_Model":
             # In reality: trigger retraining pipeline -> new model ref
             # Simulation: Bump model version in reference if possible
             exec_logic = new_node_data.get("execution_logic", {})
             if exec_logic.get("type") == "Model_Ref" and 'reference' in exec_logic:
                  parts = exec_logic["reference"].split('_v')
                  if len(parts) == 2:
                       current_model_ver = parts[1]
                       next_model_ver = self._get_next_version(current_model_ver) # Reuse version logic
                       exec_logic["reference"] = f"{parts[0]}_v{next_model_ver}"
                       adaptation_rationale += f" Updated model reference to _v{next_model_ver}."
                  else:
                       adaptation_rationale += " Could not parse model reference for version bump."
             else:
                  adaptation_rationale += " No model reference found to update."
        elif adaptation_method == "Adjust_Parameters":
            # In reality: analyze metrics, adjust params
            # Simulation: Modify a parameter slightly if exists
            exec_logic = new_node_data.get("execution_logic", {})
            params = exec_logic.get("parameters", {})
            if params:
                 param_to_adjust = random.choice(list(params.keys()))
                 current_val = params[param_to_adjust]
                 # Simple adjustment simulation
                 if isinstance(current_val, (int, float)):
                     adjustment = random.uniform(-0.1, 0.1) * current_val + random.choice([-1, 1])
                     new_val = current_val + adjustment
                     params[param_to_adjust] = round(new_val, 3) if isinstance(new_val, float) else int(new_val)
                     adaptation_rationale += f" Adjusted parameter '{param_to_adjust}' from {current_val} to {params[param_to_adjust]}."
                 else:
                     adaptation_rationale += f" Could not simulate adjustment for parameter '{param_to_adjust}' (type: {type(current_val)})."
            else:
                  adaptation_rationale += " No parameters found to adjust."
        elif adaptation_method == "Select_New_Algorithm":
             # Simulation: Change execution type or reference drastically (if alternatives known)
             adaptation_rationale += " (Simulation: Would select a new algorithm/model reference)."
        elif adaptation_method == "Trigger_Human_Review":
             adaptation_rationale += " Action required: Trigger human review process."
             # Log event but don't create new version? Or create version indicating review needed?
             # For now, we still create a new version to track the event.
        elif adaptation_method == "Evolve_Structure":
             # Simulation: Log intent (requires graph modification capabilities)
             adaptation_rationale += " (Simulation: Would trigger graph structure evolution)."
        else:
            logger.warning(f"Unsupported adaptation method: {adaptation_method}")
            adaptation_rationale += " Unsupported adaptation method."
            # Optionally skip versioning for unsupported methods?
            # return None

        # --- Auto-Versioning --- 
        original_version = new_node_data.get("version", "0.0.0")
        next_version = self._get_next_version(original_version)
        new_node_data["version"] = next_version
        
        # Update ID to reflect new version
        id_parts = original_node_id.split('_v')
        if len(id_parts) == 2:
            new_node_id = f"{id_parts[0]}_v{next_version}"
        else:
            new_node_id = f"{original_node_id}_v{next_version}" # Fallback ID
        new_node_data["@id"] = new_node_id
        
        # Update metadata
        new_node_data["rationale"] = adaptation_rationale
        new_node_data["creation_timestamp"] = self._now()
        new_node_data["author_agent_ref"] = adapting_agent_ref
        
        # Clear old adaptation strategy? Or keep it? Keep for now.
        # Optional: Add link to previous version? Add `derived_from` field?
        new_node_data["derived_from"] = original_node_id
        
        # --- Save New Node Version --- 
        new_node_filename = f"{new_node_id}.json"
        new_node_path = self.nodes_dir / new_node_filename
        try:
            # Validate before saving?
            # schema_path = Path(__file__).resolve().parent.parent / "schemas/scm_node.schema.json"
            # if not validate_node_data(new_node_data, schema_path=schema_path):
            #     logger.error(f"Generated node {new_node_id} failed validation. Aborting adaptation save.")
            #     # Log failure event?
            #     return None
                 
            with open(new_node_path, 'w') as f:
                json.dump(new_node_data, f, indent=2)
            logger.info(f"Successfully saved new node version: {new_node_path}")
            
            # --- Log Adaptation Event --- 
            log_entry = {
                 "original_node_id": original_node_id,
                 "original_version": original_version,
                 "new_node_id": new_node_id,
                 "new_version": next_version,
                 "adaptation_trigger": trigger_condition,
                 "trigger_details": trigger_details,
                 "adaptation_method": adaptation_method,
                 "method_params": method_params,
                 "rationale": adaptation_rationale,
                 "adapting_agent": adapting_agent_ref,
                 "adaptation_timestamp": new_node_data["creation_timestamp"]
            }
            self._log_adaptation_event(log_entry)
            
            return new_node_id # Return the ID of the newly created node
            
        except Exception as e:
            logger.error(f"Failed to save or log new node version {new_node_id}: {e}")
            # Clean up file if partially written?
            if new_node_path.exists():
                 try: new_node_path.unlink() 
                 except OSError: pass
            return None

    def evaluate_and_adapt(self, node_path: Path, node_data: Dict[str, Any], execution_metadata: Dict[str, Any], agent_ref: str="agent_adaptor_v1") -> Optional[str]:
        """Checks triggers based on metrics and performs adaptation if needed, using provided path and data."""
        node_id = node_data.get("@id", "unknown") # Get ID from data
        logger.debug(f"Evaluating adaptation for node {node_id} using path {node_path}")

        # File existence check might be less critical now, as path comes from orchestrator
        # but keep the explicit check for robustness maybe?
        try:
             with open(node_path, 'r') as f_check:
                 pass # Just check if it opens
             logger.debug(f"Successfully opened node file {node_path} for read check.")
        except FileNotFoundError:
             logger.error(f"Cannot adapt: Node file check FAILED (FileNotFoundError) for path {node_path}")
             return None
        except Exception as e_check:
             logger.error(f"Cannot adapt: Node file check FAILED (Error: {e_check}) for path {node_path}")
             return None

        # We already have node_data, no need to load it again
        # try:
        #     node_data = load_json_file(node_path)
        # except Exception as e:
        #      logger.error(f"Cannot adapt: Failed to load node data from {node_path}: {e}")
        #      return None
             
        triggered_strategy = self.check_adaptation_triggers(node_data, execution_metadata)
        
        if triggered_strategy:
            # Pass the already loaded node_data to perform_adaptation
            new_node_id = self.perform_adaptation(node_data, triggered_strategy, adapting_agent_ref=agent_ref)
            return new_node_id
        else:
             logger.debug(f"No adaptation triggers met for node {node_id}.")
             return None

# Example Usage (for testing manager directly)
if __name__ == "__main__":
    # Setup basic logging for testing
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create dummy nodes directory and node file for testing
    test_nodes_dir = Path("./test_scm_nodes")
    test_nodes_dir.mkdir(exist_ok=True)
    test_node_path = test_nodes_dir / "node_test_adapt_v1.0.0.json"
    dummy_node_data = {
        "@id": "node_test_adapt_v1.0.0",
        "version": "1.0.0",
        "purpose_statement": "Test node for adaptation",
        "execution_logic": {"type": "Model_Ref", "reference": "model_dummy_v1", "parameters": {"threshold": 0.5, "rate": 10}},
        "outputs": [], # Simplified for test
        "state_management": {"type": "Ephemeral"},
        "resilience_policy": [],
        "observability": {"metrics":[], "logs":{"level":"Info", "content":"Standard"}, "trace_propagation":True},
        "adaptation_strategy": {
            "trigger": "Performance_Degradation",
            "metric_ref": "metric_def_confidence_v1.0.0", # Example
            "method": "Adjust_Parameters",
            "method_params": {"adjustment_factor": 0.05}
        },
        "rationale": "Initial test node.",
        "author_agent_ref": "user_init",
        "creation_timestamp": datetime.now(timezone.utc).isoformat()
    }
    with open(test_node_path, 'w') as f:
        json.dump(dummy_node_data, f, indent=2)
        
    # Initialize manager
    manager = AdaptationManager(str(test_nodes_dir), adaptation_log_path="./test_adaptation_log.jsonl")
    
    # Simulate execution metadata indicating low confidence
    test_metadata_low_conf = {
        "execution_duration_ms": 250.5,
        "simulated_confidence": 0.6 # Below threshold PERFORMANCE_CONFIDENCE_THRESHOLD = 0.75
    }
    
    print("\n--- Testing Low Confidence Trigger ---")
    new_node_id_1 = manager.evaluate_and_adapt(test_node_path, dummy_node_data, test_metadata_low_conf)
    if new_node_id_1:
         print(f"Adaptation successful! New node created: {new_node_id_1}")
    else:
         print("No adaptation performed.")
         
    # Simulate high execution time
    test_metadata_high_time = {
        "execution_duration_ms": 1500.0, # Above threshold PERFORMANCE_TIME_THRESHOLD_MS = 1000
        "simulated_confidence": 0.9
    }
    
    # Use the previously created node if it exists, otherwise original
    adapt_node_id = new_node_id_1 or "node_test_adapt_v1.0.0"
    print(f"\n--- Testing High Execution Time Trigger on {adapt_node_id} ---")
    new_node_id_2 = manager.evaluate_and_adapt(test_node_path, dummy_node_data, test_metadata_high_time)
    if new_node_id_2:
         print(f"Adaptation successful! New node created: {new_node_id_2}")
    else:
         print("No adaptation performed.")

    # Simulate no trigger
    test_metadata_ok = {
        "execution_duration_ms": 150.0,
        "simulated_confidence": 0.95
    }
    adapt_node_id_final = new_node_id_2 or adapt_node_id
    print(f"\n--- Testing No Trigger on {adapt_node_id_final} ---")
    new_node_id_3 = manager.evaluate_and_adapt(test_node_path, dummy_node_data, test_metadata_ok)
    if new_node_id_3:
         print(f"Adaptation successful! New node created: {new_node_id_3}")
    else:
         print("No adaptation performed (as expected).")
         
    print(f"\nAdaptation log created at: {manager.adaptation_log_path}")
    # Clean up test files/dir? 