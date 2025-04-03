import time
import logging
import importlib # For dynamic imports
import importlib.util # Import the util submodule
from pathlib import Path
from typing import Dict, Any, Optional, List # Added List
import sys
import random # For generating mock data

# Use absolute imports
from scm.runtime.utils import (
    load_json_file,
    validate_node_data,
    simulate_model_execution, # Keep for fallback
    simulate_subgraph_execution,
    simulate_external_call,
    # report_metric # Keep only if utils logs metrics independently
)
from scm.monitoring.tracer import log_trace_event

# Set up logger for the engine
logger = logging.getLogger(__name__)
# Ensure utils logger is also configured if running this file directly
# (basicConfig in utils should handle this if it's imported)

class SCMExecutionEngine:
    """Core engine for executing a single SCM node."""

    def __init__(self, node_path: str):
        """Initialize the engine with the path to the node JSON file."""
        self.node_path = Path(node_path)
        self.node_data: Dict[str, Any] = {}
        self.execution_result: Dict[str, Any] = {}
        self.execution_metadata: Dict[str, Any] = {}
        # Add node_id storage for easier logging
        self.node_id: str = "unknown_node"

    def _setup_logging(self):
        """Configure logging based on the node's observability settings."""
        log_config = self.node_data.get("observability", {}).get("logs", {})
        level_str = log_config.get("level", "Info").upper()
        level = getattr(logging, level_str, logging.INFO) # Default to INFO
        
        # Update the logger level for this specific engine instance/run
        # Note: BasicConfig sets the root logger. For more granular control,
        # consider creating specific handlers and formatters.
        logging.getLogger().setLevel(level) # Adjust root logger level for simplicity here
        logger.info(f"Logging level set to {level_str} based on node configuration.")

    def load_and_validate_node(self) -> bool:
        """Loads the node JSON and validates it against the schema."""
        logger.info(f"Loading node from: {self.node_path}")
        try:
            self.node_data = load_json_file(self.node_path)
            self.node_id = self.node_data.get("@id", "unknown_node") # Store node_id
            log_trace_event("NODE_LOAD_START", {"path": str(self.node_path)}, self.node_id)
            logger.info(f"Successfully loaded node: {self.node_id}")
            
            schema_path = Path(__file__).resolve().parent.parent / "schemas/scm_node.schema.json"
            is_valid = validate_node_data(self.node_data, schema_path=schema_path)
            if not is_valid:
                logger.error("Node validation failed. Cannot execute.")
                log_trace_event("NODE_LOAD_FAILED", {"reason": "Validation failed"}, self.node_id)
                return False
            
            log_trace_event("NODE_LOAD_SUCCESS", {"node_id": self.node_id}, self.node_id)
            self._setup_logging() # Configure logging based on loaded node
            return True
            
        except Exception as e:
            logger.exception(f"Failed to load or validate node: {e}")
            log_trace_event("NODE_LOAD_FAILED", {"reason": str(e)}, self.node_id)
            return False

    def _generate_mock_input_data(self, input_defs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generates mock data based on input definitions."""
        mock_inputs = {}
        for inp in input_defs:
            input_name = inp.get("input_name")
            data_type = inp.get("data_type_ref", "")
            if not input_name:
                continue

            # Simple mock data generation based on type hints
            if "timeseries" in data_type.lower():
                mock_inputs[input_name] = [random.randint(50, 150) for _ in range(random.randint(5, 15))]
            elif "scalar_float" in data_type.lower():
                mock_inputs[input_name] = round(random.uniform(0.0, 100.0), 4)
            elif "scalar_int" in data_type.lower():
                 mock_inputs[input_name] = random.randint(0, 1000)
            elif "string" in data_type.lower():
                mock_inputs[input_name] = f"mock_string_data_{random.randint(100, 999)}"
            elif "boolean" in data_type.lower():
                 mock_inputs[input_name] = random.choice([True, False])
            elif "dict" in data_type.lower() or "object" in data_type.lower():
                 mock_inputs[input_name] = {"mock_key": f"value_{random.randint(1,5)}", "mock_flag": random.choice([True, False])}
            else:
                 # Default fallback for unknown types
                 mock_inputs[input_name] = f"mock_data_for_{input_name}"

            logger.debug(f"Generated mock input '{input_name}' (type: {data_type}): {str(mock_inputs[input_name])[:100]}...") # Log truncated data
        return mock_inputs

    def _execute_real_model(self, model_ref: str, inputs: dict, params: dict) -> Optional[Dict[str, Any]]:
        """Loads and runs a real model module, validating outputs."""
        model_module = None
        spec = None
        module_name = f"scm_models_dynamic.{model_ref}" # Define name early for logging
        # --- Load Model ---
        try:
            engine_dir = Path(__file__).resolve().parent
            models_dir = engine_dir.parent / "models"
            model_file_path = models_dir / f"{model_ref}.py"
            logger.info(f"Attempting to load real model from file path: {model_file_path}")

            if not model_file_path.is_file():
                logger.warning(f"Model file not found at {model_file_path}. Falling back.")
                return None # Signal fallback

            spec = importlib.util.spec_from_file_location(module_name, model_file_path)
            if spec and spec.loader:
                model_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(model_module)
                logger.info(f"Successfully loaded model module {module_name} from path.")
            else:
                 logger.error(f"Could not create module spec/loader for {model_file_path}.")
                 return None # Failure

        except Exception as e:
            logger.error(f"Error loading model {model_ref} from path: {e}", exc_info=True)
            log_trace_event("NODE_ERROR", {"error": f"Real model loading failed: {e}"}, self.node_id)
            return None # Failure

        # --- Execute Loaded Model --- 
        if model_module and hasattr(model_module, 'run_model') and callable(model_module.run_model):
            try:
                 logger.info(f"Executing run_model function in {module_name}")
                 model_output = model_module.run_model(inputs, params) # Pass generated inputs

                 if not isinstance(model_output, dict):
                     logger.error(f"Model {module_name}.run_model did not return a dictionary.")
                     return None # Failure

                 # --- Validate Output Keys ---
                 expected_outputs = {out.get('output_name') for out in self.node_data.get("outputs", []) if out.get('output_name')}
                 actual_keys = set(model_output.keys())
                 is_valid_output = expected_outputs.issubset(actual_keys)

                 if is_valid_output:
                     logger.info(f"Model output validation passed. Expected keys present: {expected_outputs}")
                     # Set execution mode here upon successful validation
                     self.execution_metadata["execution_mode"] = "real_model_success"
                     # Extract confidence
                     if "confidence" in model_output:
                          self.execution_metadata["confidence_source"] = "model"
                          self.execution_metadata["simulated_confidence"] = model_output["confidence"]
                     elif "forecast_confidence" in model_output: # Specific key from dummy model
                           self.execution_metadata["confidence_source"] = "model"
                           self.execution_metadata["simulated_confidence"] = model_output["forecast_confidence"]
                     elif "prediction_confidence" in model_output: # Specific key from random model
                            self.execution_metadata["confidence_source"] = "model"
                            self.execution_metadata["simulated_confidence"] = model_output["prediction_confidence"]
                     else:
                           self.execution_metadata["confidence_source"] = "none"
                     return model_output # Return the valid output
                 else:
                     missing_keys = expected_outputs - actual_keys
                     logger.error(f"Model output validation FAILED. Missing expected keys: {missing_keys}. Expected: {expected_outputs}, Got: {actual_keys}")
                     log_trace_event("NODE_ERROR", {"error": "Real model output validation failed", "missing_keys": list(missing_keys)}, self.node_id)
                     return None # Failure due to invalid output

            except Exception as e:
                 logger.error(f"Error executing run_model in {module_name}: {e}", exc_info=True)
                 log_trace_event("NODE_ERROR", {"error": f"Real model execution failed: {e}"}, self.node_id)
                 return None # Failure during execution
        else:
             logger.error(f"Module {module_name} loaded, but missing callable 'run_model' function.")
             return None # Failure

    def execute(self, external_inputs: Optional[Dict[str, Any]] = None) -> bool:
        """Executes the node, using external inputs if provided, else generating mocks."""
        if not self.node_data:
            logger.error("Node data not loaded. Cannot execute.")
            return False

        logger.info(f"Starting execution for node: {self.node_id}")
        log_trace_event("NODE_EXEC_START", {}, self.node_id)
        start_time = time.time()

        exec_logic = self.node_data.get("execution_logic")
        if not exec_logic:
            error_msg = "Missing 'execution_logic' in node data."
            logger.error(error_msg)
            log_trace_event("NODE_ERROR", {"error": error_msg}, self.node_id)
            self.execution_result = {"error": error_msg}
            return False

        exec_type = exec_logic.get("type")
        reference = exec_logic.get("reference")
        params = exec_logic.get("parameters", {})
        node_input_defs = self.node_data.get("inputs", [])
        node_output_defs = self.node_data.get("outputs", [])

        try:
            result = None
            inputs_for_execution = {}
            input_source = "none"

            # --- Determine Inputs --- 
            if external_inputs is not None:
                 required_input_names = {inp.get("input_name") for inp in node_input_defs if inp.get("input_name")}
                 inputs_for_execution = {k: v for k, v in external_inputs.items() if k in required_input_names}
                 input_source = "composer"
                 logger.debug(f"Using inputs provided by composer: {list(inputs_for_execution.keys())}")
                 provided_keys = set(inputs_for_execution.keys())
                 if provided_keys != required_input_names:
                      logger.warning(f"Mismatch between required inputs ({required_input_names}) and provided inputs ({provided_keys}) for node {self.node_id}")
            else:
                 input_source = "generated_mock"
                 inputs_for_execution = self._generate_mock_input_data(node_input_defs)
                 logger.debug(f"Generated mock inputs: {list(inputs_for_execution.keys())}")
            
            # Log input structure and source
            log_trace_event("NODE_INPUTS", {"inputs_structure": {k: type(v).__name__ for k,v in inputs_for_execution.items()}, "source": input_source}, self.node_id)

            # --- Execute Logic --- 
            if exec_type == "Model_Ref":
                self.execution_metadata["execution_mode"] = "real_model_attempt"
                result = self._execute_real_model(reference, inputs_for_execution, params)

                if result is None: # Fallback
                     self.execution_metadata["execution_mode"] = "simulation_fallback"
                     logger.info(f"Falling back to simulation for model {reference}.")
                     simulated_inputs = {inp["input_name"]: f"mock_data_for_{inp['input_name']}"
                                         for inp in node_input_defs}
                     log_trace_event("NODE_INPUTS", {"inputs": simulated_inputs, "source": "simulation_fallback"}, self.node_id)
                     result = simulate_model_execution(reference, simulated_inputs, params, node_output_defs)
                     if "confidence" in result:
                          self.execution_metadata["confidence_source"] = "simulation"
                          self.execution_metadata["simulated_confidence"] = result.get("confidence")
                     else:
                          self.execution_metadata["confidence_source"] = "none"

            elif exec_type == "Subgraph_Ref" or exec_type == "External_Call":
                self.execution_metadata["execution_mode"] = "simulation"
                logger.debug(f"Passing inputs to simulation for {exec_type}: {list(inputs_for_execution.keys())}")
                if exec_type == "Subgraph_Ref":
                    result = simulate_subgraph_execution(reference, inputs_for_execution, node_output_defs)
                else: # External_Call
                    result = simulate_external_call(reference, inputs_for_execution, params, node_output_defs)
            else:
                error_msg = f"Unsupported execution type: {exec_type}"
                logger.warning(error_msg)
                log_trace_event("NODE_ERROR", {"error": error_msg}, self.node_id)
                self.execution_result = {"error": error_msg}
                log_trace_event("NODE_EXEC_END", {"status": "FAILED", "error": error_msg}, self.node_id)
                return False

            # --- Process Result ---
            if result is None:
                error_msg = f"Execution failed for node {self.node_id} (Mode: {self.execution_metadata.get('execution_mode', 'unknown')})."
                logger.error(error_msg)
                log_trace_event("NODE_ERROR", {"error": "Execution failed"}, self.node_id)
                self.execution_result = {"error": error_msg}
                log_trace_event("NODE_EXEC_END", {"status": "FAILED", "error": error_msg}, self.node_id)
                return False

            self.execution_result = result
            log_trace_event("NODE_OUTPUTS", {"outputs": result}, self.node_id)
            logger.info(f"Execution successful for node {self.node_id} (Mode: {self.execution_metadata.get('execution_mode')}).")

            # Handle observability
            self._handle_observability(start_time, result)
            log_trace_event("NODE_EXEC_END", {"status": "SUCCESS"}, self.node_id)
            return True

        except Exception as e:
            logger.exception(f"An unexpected error occurred during node execution: {e}")
            error_msg = str(e)
            log_trace_event("NODE_ERROR", {"error": error_msg}, self.node_id)
            log_trace_event("NODE_EXEC_END", {"status": "FAILED", "error": error_msg}, self.node_id)
            self.execution_result = {"error": error_msg}
            return False

    def _handle_observability(self, start_time: float, result: Dict[str, Any]):
        """Handles logging metrics and trace information post-execution."""
        end_time = time.time()
        duration = end_time - start_time
        duration_ms = duration * 1000
        self.execution_metadata["execution_duration_ms"] = duration_ms
        logger.info(f"Node execution completed in {duration:.3f} seconds.")
        log_trace_event("NODE_METRIC", {"metric_name": "execution_duration_ms", "value": duration_ms}, self.node_id)

        obs_config = self.node_data.get("observability", {})
        
        # Report Metrics 
        # Confidence is now stored in self.execution_metadata["simulated_confidence"]
        # regardless of source (real model, simulation, or none)
        confidence = self.execution_metadata.get("simulated_confidence")
        if confidence is not None:
             log_trace_event("NODE_METRIC", {"metric_name": "confidence", "value": confidence, "source": self.execution_metadata.get("confidence_source", "unknown")}, self.node_id)
             for metric in obs_config.get("metrics", []):
                 metric_ref = metric.get("metric_ref")
                 if "confidence" in metric_ref.lower(): 
                     log_trace_event("NODE_METRIC", {"metric_name": metric_ref, "value": confidence}, self.node_id)
        
        # Report execution time metric if specified
        for metric in obs_config.get("metrics", []):
             metric_ref = metric.get("metric_ref")
             if "exec_time" in metric_ref.lower():
                  log_trace_event("NODE_METRIC", {"metric_name": metric_ref, "value": duration}, self.node_id)

        # Trace Propagation (Simulated / Checked by Composer/Agent)
        # The engine itself doesn't propagate, just notes if it should
        if obs_config.get("trace_propagation", False):
            # The actual trace ID is managed by the caller (Composer/Agent)
            # We just log that this node supports it.
            log_trace_event("TRACE_PROPAGATION_ENABLED", {}, self.node_id)
            logger.info("Trace Propagation Enabled for this node.")
        else:
            logger.info("Trace Propagation Disabled for this node.")
            
    def get_result(self) -> Dict[str, Any]:
        """Returns the execution result."""
        return self.execution_result

    def get_metadata(self) -> Dict[str, Any]:
        """Returns execution metadata (duration, confidence, trace id)."""
        return self.execution_metadata

# Example Usage (can be run directly for testing)
if __name__ == "__main__":
    # Configure root logger for direct script execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Assumes script is run from the scm/ directory
    # Adjust path if running from root or elsewhere
    example_node_path = Path("../nodes/forecast_sales_v2.1.0.json") # Relative path from scm/runtime
    
    if not example_node_path.exists():
         # Try path relative to project root if running from there
         alt_path = Path("scm/nodes/forecast_sales_v2.1.0.json")
         if alt_path.exists():
             example_node_path = alt_path
         else: 
            logger.error(f"Example node file not found at {example_node_path} or {alt_path}. Please check the path.")
            exit(1)
            
    engine = SCMExecutionEngine(str(example_node_path))
    
    logger.info("--- Loading and Validating Node ---")
    if engine.load_and_validate_node():
        logger.info("--- Executing Node ---")
        if engine.execute():
            logger.info("--- Execution Result ---")
            print(json.dumps(engine.get_result(), indent=2))
            logger.info("--- Execution Metadata ---")
            print(json.dumps(engine.get_metadata(), indent=2))
        else:
            logger.error("Node execution failed.")
            print(json.dumps(engine.get_result(), indent=2)) # Print error result
    else:
        logger.error("Node loading or validation failed.") 