import uuid
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class SCMTracer:
    """Manages trace sessions and logs execution events for SCM graphs."""

    def __init__(self, output_dir: str = "./scm_traces", session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.trace_file_path = self.output_dir / f"trace_{self.session_id}.jsonl"
        self.session_data: Dict[str, Any] = {
            "trace_id": self.session_id,
            "start_time": self._now(),
            "end_time": None,
            "status": "RUNNING",
            "nodes_executed": [],
            "error_events": [],
            "agent_decisions": [],
            "final_results": None
        }
        self._log_to_console(f"Tracer initialized. Session ID: {self.session_id}. Log file: {self.trace_file_path}")

    def _now(self) -> str:
        """Returns the current time in ISO format with UTC timezone."""
        return datetime.now(timezone.utc).isoformat()

    def _log_to_console(self, message: str, level: int = logging.INFO):
        """Helper to log messages to console via logger."""
        logger.log(level, f"[Tracer:{self.session_id[:8]}] {message}")

    def _write_event(self, event_data: Dict[str, Any]):
        """Appends a JSON event to the trace file."""
        try:
            with open(self.trace_file_path, 'a') as f:
                json.dump(event_data, f)
                f.write('\n')
        except Exception as e:
            self._log_to_console(f"Error writing event to trace file: {e}", logging.ERROR)

    def log_event(self, event_type: str, data: Dict[str, Any], node_id: Optional[str] = None):
        """Logs a generic event."""
        event = {
            "timestamp": self._now(),
            "trace_id": self.session_id,
            "event_type": event_type,
            "node_id": node_id,
            "data": data
        }
        self._write_event(event)
        self._log_to_console(f"Event: {event_type} {f'(Node: {node_id})' if node_id else ''} Data: {json.dumps(data)}", logging.DEBUG)
        
        # Update session data based on event type
        if event_type == "AGENT_DECISION":
            self.session_data["agent_decisions"].append({"timestamp": event["timestamp"], "decision": data})
        elif event_type == "NODE_ERROR" or data.get("status") == "FAILED":
             self.session_data["error_events"].append({"timestamp": event["timestamp"], "node_id": node_id, "error": data.get("error", "Unknown")})
        elif event_type == "NODE_END" and node_id:
             if node_id not in self.session_data["nodes_executed"]:
                  self.session_data["nodes_executed"].append(node_id)

    def start_trace(self, graph_info: Optional[Dict[str, Any]] = None):
        """Logs the start of a graph execution trace."""
        self.log_event("GRAPH_START", {"message": "Graph execution started.", "graph_info": graph_info or {}})
        self._log_to_console("Graph trace started.")

    def end_trace(self, status: str, final_results: Optional[Dict[str, Any]] = None):
        """Logs the end of a graph execution trace and saves session summary."""
        self.session_data["end_time"] = self._now()
        self.session_data["status"] = status
        self.session_data["final_results"] = final_results
        self.log_event("GRAPH_END", {"message": f"Graph execution ended with status: {status}", "final_status": status})
        self._log_to_console(f"Graph trace ended. Status: {status}")
        
        # Optionally save the session summary to a separate file or log it
        summary_path = self.output_dir / f"summary_{self.session_id}.json"
        try:
            with open(summary_path, 'w') as f:
                json.dump(self.session_data, f, indent=2)
            self._log_to_console(f"Trace summary saved to: {summary_path}")
        except Exception as e:
            self._log_to_console(f"Error saving trace summary: {e}", logging.ERROR)
            
    def get_trace_id(self) -> str:
         return self.session_id

# --- Global Tracer Instance (Simple Approach) ---
# Using a global instance can simplify integration but has drawbacks in complex/concurrent scenarios.
# Consider dependency injection or context management for more robust applications.
_active_tracer: Optional[SCMTracer] = None

def initialize_tracer(output_dir: str = "./scm_traces") -> SCMTracer:
    global _active_tracer
    _active_tracer = SCMTracer(output_dir=output_dir)
    return _active_tracer

def get_tracer() -> Optional[SCMTracer]:
    """Gets the currently active global tracer instance."""
    if _active_tracer is None:
         logger.warning("Tracer accessed before initialization. Call initialize_tracer() first.")
         # Initialize implicitly for convenience? Or raise error?
         # initialize_tracer() # Implicit initialization
    return _active_tracer

def log_trace_event(event_type: str, data: Dict[str, Any], node_id: Optional[str] = None):
     """Helper function to log an event using the global tracer."""
     tracer = get_tracer()
     if tracer:
          tracer.log_event(event_type, data, node_id)
          
# Example Usage (for testing tracer directly)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    tracer = initialize_tracer()
    tracer.start_trace(graph_info={"name": "test_graph", "node_count": 3})
    
    # Simulate node executions
    tracer.log_event("NODE_START", {"message": "Starting node 1"}, "node_1")
    # Simulate some work
    tracer.log_event("NODE_METRIC", {"metric_name": "confidence", "value": 0.95}, "node_1")
    tracer.log_event("NODE_END", {"status": "SUCCESS", "outputs": {"result": 123}}, "node_1")
    
    tracer.log_event("AGENT_DECISION", {"decision": "Proceeding with node 2", "reason": "Confidence above threshold"})
    
    tracer.log_event("NODE_START", {"message": "Starting node 2"}, "node_2")
    tracer.log_event("NODE_ERROR", {"error": "Service unavailable", "details": "Connection timeout"}, "node_2")
    tracer.log_event("NODE_END", {"status": "FAILED", "error": "Service unavailable"}, "node_2")

    tracer.end_trace(status="FAILED", final_results=None)

    print(f"\nTrace log created at: {tracer.trace_file_path}")
    print(f"Trace summary created at: {tracer.output_dir / f'summary_{tracer.session_id}.json'}") 