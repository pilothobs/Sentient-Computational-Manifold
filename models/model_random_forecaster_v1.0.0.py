import logging
import random
import time

logger = logging.getLogger(__name__)

def run_model(inputs: dict, params: dict) -> dict:
    """ 
    Dummy random forecaster model.
    Generates random outputs, ignoring inputs/params mostly.
    """
    logger.info(f"--- Running Dummy Model: model_random_forecaster_v1.0.0 ---")
    logger.info(f"Received inputs: {list(inputs.keys())}")
    logger.info(f"Received parameters: {params}")
    
    # Simulate processing time
    time.sleep(random.uniform(0.01, 0.05))
    
    # Generate mock forecast data
    horizon = params.get("prediction_horizon", 3) # Use parameter if provided
    forecast = [random.randint(50, 200) for _ in range(horizon)]
    
    # Generate mock confidence
    confidence = random.uniform(0.5, 0.99)
    
    output = {
        "random_forecast": forecast,
        "prediction_confidence": round(confidence, 4)
        # Note: Output keys differ from the LSTM model and node
    }
    
    logger.info(f"Dummy model finished. Output: {output}")
    logger.info(f"--- End Dummy Model Run ---")
    
    return output

# Example usage if run directly
if __name__ == "__main__":
     logging.basicConfig(level=logging.INFO)
     dummy_inputs = {"some_input": "data"}
     dummy_params = {"prediction_horizon": 5}
     result = run_model(dummy_inputs, dummy_params)
     print("\nDirect run result:")
     print(result) 