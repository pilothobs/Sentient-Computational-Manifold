import logging
import random
import time

logger = logging.getLogger(__name__)

def run_model(input_dict: dict, parameters: dict) -> dict:
    """ 
    Dummy function simulating a real LSTM sales forecasting model.
    Takes input data and parameters, returns mocked forecast and confidence.
    """
    logger.info(f"--- Running Dummy Model: model_lstm_sales_predictor_v3.2.0 ---")
    logger.info(f"Received inputs: {list(input_dict.keys())}")
    logger.info(f"Received parameters: {parameters}")
    
    # Simulate processing based on inputs/params (very basic)
    lookback = parameters.get("lookback_window", 1)
    horizon = parameters.get("prediction_horizon", 1)
    input_length = sum(len(str(v)) for v in input_dict.values()) # Simple hash of input
    
    # Simulate processing time
    time.sleep(random.uniform(0.05, 0.2))
    
    # Generate mock forecast data
    # Make forecast slightly dependent on input length and params
    base_value = (input_length % 50) + 100 + lookback
    forecast = [round(base_value + random.uniform(-10, 10) * (i+1)) for i in range(horizon)]
    
    # Generate mock confidence - FORCED LOW FOR TESTING
    # confidence = max(0.5, min(0.99, 0.95 - (lookback / 200.0) - (horizon / 100.0) + random.uniform(-0.05, 0.05)))
    confidence = 0.7 # Force low confidence
    logger.warning(f"Forcing low confidence for testing: {confidence}")
    
    output = {
        "monthly_forecast": forecast,
        "forecast_confidence": round(confidence, 4)
        # Note: The output keys should ideally match the 'outputs' defined 
        # in the corresponding node JSON (e.g., forecast_sales_v2.1.0.json)
    }
    
    logger.info(f"Dummy model finished. Output: {output}")
    logger.info(f"--- End Dummy Model Run ---")
    
    return output

# Example usage if run directly
if __name__ == "__main__":
     logging.basicConfig(level=logging.INFO)
     dummy_inputs = {"processed_history": "long_time_series_data...", "market_data": "some_indicators..."}
     dummy_params = {"lookback_window": 12, "prediction_horizon": 3}
     result = run_model(dummy_inputs, dummy_params)
     print("\nDirect run result:")
     print(result) 