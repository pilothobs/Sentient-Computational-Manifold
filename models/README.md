# SCM Model Modules

This directory contains the implementations of executable models referenced by SCM nodes with `"execution_logic.type": "Model_Ref"`.

## Purpose

Each Python file (`.py`) in this directory represents a specific version of an executable model or algorithm. The SCM Execution Engine (`scm/runtime/engine.py`) dynamically loads and executes these modules based on the `reference` field in a node's `execution_logic`.

## Interface Requirements

To be compatible with the SCM Execution Engine, each model module **MUST**:

1.  Be a standard Python file (`.py`).
2.  Define a function with the exact signature:
    ```python
    def run_model(inputs: dict, params: dict) -> dict:
        # ... model logic ...
        return output_dict
    ```
3.  **`inputs`**: A dictionary where keys match the `input_name` fields defined in the calling SCM node's `inputs` array. The values will be the (currently simulated) data passed by the engine for those inputs.
4.  **`params`**: A dictionary containing the key-value pairs defined in the calling SCM node's `execution_logic.parameters` field.
5.  **Return Value**: The function **MUST** return a dictionary. The keys in this dictionary should ideally correspond to the `output_name` fields defined in the calling SCM node's `outputs` array. This dictionary represents the result of the model execution.

## Example Output Format

The returned dictionary should contain the results of the model's computation. If the model calculates metrics like confidence, include them directly in the output dictionary. The engine specifically looks for keys like `confidence` or `forecast_confidence` to update execution metadata.

```python
# Example output from a forecasting model
output = {
    "monthly_forecast": [150, 165, 180],  # Corresponds to an output named 'monthly_forecast'
    "forecast_confidence": 0.85           # Corresponds to an output named 'forecast_confidence'
}
return output
```

## File Naming and Versioning

- **Filename Convention**: Model files should be named according to the reference used in the SCM node, following the pattern: `<model_name>_v<major>.<minor>.<patch>.py`.
- **Reference Matching**: The `execution_logic.reference` in the SCM node JSON (e.g., `"model_lstm_sales_predictor_v3.2.0"`) must exactly match the filename excluding the `.py` extension.
- **Versioning**: Use semantic versioning (Major.Minor.Patch) to track changes and allow the SCM system (especially the Adaptation Manager) to reference and manage different model versions.

## Dynamic Loading

The SCM Execution Engine uses `importlib.util` to load these modules dynamically based on the file path derived from the `reference`. Ensure the `scm` directory is part of the Python path (e.g., via `PYTHONPATH` or project structure) for these imports to work correctly. 