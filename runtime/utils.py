import json
import logging
import time
import random
from pathlib import Path
from typing import Dict, Any, List
from jsonschema import validate, ValidationError

logger = logging.getLogger(__name__)

def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Loads a JSON file from the given path."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"JSON file not found: {file_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {file_path}: {e}")
        raise
    except Exception as e:
         logger.error(f"An unexpected error occurred loading {file_path}: {e}")
         raise

def validate_node_data(node_data: Dict[str, Any], schema_path: Path = None) -> bool:
    """Validates node data against the SCM node schema."""
    if schema_path is None:
        # Default schema path relative to this utils file
        schema_path = Path(__file__).resolve().parent.parent / "schemas/scm_node.schema.json"
        
    if not schema_path.exists():
         logger.error(f"Schema file not found at {schema_path}. Cannot validate.")
         return False
         
    try:
        schema = load_json_file(schema_path)
        validate(instance=node_data, schema=schema)
        logger.info(f"Node data validation successful against schema: {schema_path.name}")
        return True
    except ValidationError as e:
        logger.error(f"Node data validation failed: {e.message}")
        return False
    except Exception as e:
         logger.error(f"An unexpected error occurred during validation: {e}")
         return False

# --- Simulation Functions --- 

def _generate_mock_output_value(data_type_ref: str) -> Any:
    """Generates a single mock value based on data type reference."""
    if "timeseries" in data_type_ref.lower():
        return [random.randint(50, 150) for _ in range(random.randint(3, 7))] # Shorter for output
    elif "scalar_float" in data_type_ref.lower():
        return round(random.uniform(0.0, 1.0), 4) # Common for confidence
    elif "scalar_int" in data_type_ref.lower():
         return random.randint(100, 500)
    elif "string" in data_type_ref.lower():
        return f"mock_result_string_{random.randint(1000, 9999)}"
    elif "boolean" in data_type_ref.lower():
         return random.choice([True, False])
    elif "dict" in data_type_ref.lower() or "object" in data_type_ref.lower():
         return {"sim_key": f"sim_val_{random.randint(1,5)} ", "status": "generated"}
    else:
         return f"mock_output_for_{data_type_ref}"

def _simulate_execution(exec_type: str, reference: str, params: dict, output_defs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generic simulation helper that generates outputs based on definitions."""
    logger.info(f"Simulating execution for {exec_type} '{reference}' with params: {params}")
    # Simulate some processing time
    time.sleep(random.uniform(0.1, 0.5))
    
    simulated_results = {}
    has_confidence = False
    for output_def in output_defs:
        output_name = output_def.get("output_name")
        data_type = output_def.get("data_type_ref", "")
        if output_name:
            simulated_results[output_name] = _generate_mock_output_value(data_type)
            if "confidence" in output_name.lower(): # Check if this output IS confidence
                 has_confidence = True
                 
    # Ensure a confidence metric is always present for simulation if not generated
    # Use a generic key if no specific confidence output was defined
    if not has_confidence:
         conf_key = "confidence" # Default key
         for key in simulated_results.keys(): # Check if *any* key has confidence
             if "confidence" in key.lower():
                  conf_key = None # Found one, don't add generic
                  break
         if conf_key:
             simulated_results[conf_key] = round(random.uniform(0.5, 0.99), 4)
             
    logger.info(f"Simulated {exec_type} execution complete. Outputs: {list(simulated_results.keys())}")
    return simulated_results

def simulate_model_execution(reference: str, inputs: dict, params: dict, output_defs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Simulates the execution of a model node."""
    # Model simulation might have more complex logic later, but uses helper for now
    return _simulate_execution("model", reference, params, output_defs)

def simulate_subgraph_execution(reference: str, inputs: dict, output_defs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Simulates the execution of a subgraph node."""
    # Subgraph simulation would involve recursive call to composer/engine
    # For now, just generate mock outputs based on definition
    return _simulate_execution("subgraph", reference, {}, output_defs)

def simulate_external_call(reference: str, inputs: dict, params: dict, output_defs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Simulates an external API call."""
    # External call simulation generates outputs matching the definition
    return _simulate_execution("external API call", reference, params, output_defs)

# Optional: Keep independent metric reporting if needed outside engine
# def report_metric(metric_ref: str, value: Any):
#     logger.info(f"[METRIC] {metric_ref}: {value}")
#     # Placeholder for sending to a real monitoring system