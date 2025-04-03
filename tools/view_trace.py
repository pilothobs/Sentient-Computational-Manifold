#!/usr/bin/env python
import argparse
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
import sys

def format_timestamp(iso_str):
    """Formats ISO timestamp for display."""
    if not iso_str: return "N/A"
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        # Convert to local timezone for display?
        # dt = dt.astimezone()
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] # Milliseconds
    except (ValueError, TypeError):
        return iso_str # Return original if parsing fails

def parse_jsonl(file_path: Path) -> list:
    """Parses a JSONL file line by line."""
    events = []
    try:
        with open(file_path, 'r') as f:
            for i, line in enumerate(f):
                try:
                    if line.strip():
                        events.append(json.loads(line))
                except json.JSONDecodeError:
                    print(f"Warning: Skipping malformed JSON on line {i+1} in {file_path.name}", file=sys.stderr)
    except FileNotFoundError:
        print(f"Error: Trace file not found: {file_path}", file=sys.stderr)
        return []
    except Exception as e:
         print(f"Error reading trace file {file_path}: {e}", file=sys.stderr)
         return []
    return events

def print_report(trace_id: str, events: list, summary: dict):
    """Prints a human-readable report from trace events and summary."""
    print("="*70)
    print(f" SCM Execution Trace Report")
    print("="*70)
    print(f"Trace ID: {trace_id}")
    print(f"Status:   {summary.get('status', 'UNKNOWN')}")
    print(f"Started:  {format_timestamp(summary.get('start_time'))}")
    print(f"Ended:    {format_timestamp(summary.get('end_time'))}")
    
    start_dt = datetime.fromisoformat(summary.get('start_time').replace('Z', '+00:00')) if summary.get('start_time') else None
    end_dt = datetime.fromisoformat(summary.get('end_time').replace('Z', '+00:00')) if summary.get('end_time') else None
    duration_s = (end_dt - start_dt).total_seconds() if start_dt and end_dt else None
    print(f"Duration: {duration_s:.3f} seconds" if duration_s is not None else "N/A")
    print(f"Nodes Executed: {len(summary.get('nodes_executed', []))} ({summary.get('nodes_executed', [])})")
    print(f"Errors:   {len(summary.get('error_events', []))}")
    print(f"Agent Decisions Logged: {len(summary.get('agent_decisions', []))}")
    
    print("-"*70)
    print(" Execution Timeline & Details")
    print("-"*70)

    # Sort events by timestamp primarily, add sequence if needed
    events.sort(key=lambda x: x.get('timestamp', ''))

    node_metrics = defaultdict(lambda: {'duration_ms': None, 'confidence': None})
    node_status = {}
    fallback_triggered = False # Track if fallback was suggested/occurred

    for event in events:
        ts = format_timestamp(event.get('timestamp'))
        etype = event.get('event_type', 'UNKNOWN')
        node = event.get('node_id')
        data = event.get('data', {})
        
        prefix = f"[{ts}]"
        indent = "  "
        node_prefix = f" {node}:" if node else " GRAPH:"
        
        if etype == "GRAPH_START":
            print(f"{prefix} {node_prefix} Execution Started")
        elif etype == "GRAPH_END":
            print(f"{prefix} {node_prefix} Execution Ended (Status: {data.get('final_status', '?')})")
        elif etype == "NODE_START" or etype == "NODE_LOAD_START":
            print(f"{prefix} {node_prefix} Starting Load/Execution...")
        elif etype == "NODE_END":
             status = data.get('status', 'UNKNOWN')
             node_status[node] = status
             print(f"{prefix} {node_prefix} Finished (Status: {status})")
             if 'outputs' in data:
                 print(f"{indent * 2}Outputs: {json.dumps(data['outputs'])}")
             if 'error' in data:
                  print(f"{indent * 2}Error: {data['error']}")
        elif etype == "NODE_ERROR":
             print(f"{prefix} {node_prefix} ERROR: {data.get('error')} {data.get('details', '')}")
             node_status[node] = "FAILED"
        elif etype == "NODE_METRIC":
             m_name = data.get('metric_name')
             m_val = data.get('value')
             print(f"{prefix} {node_prefix} Metric: {m_name} = {m_val:.3f}" if isinstance(m_val, float) else f"{prefix} {node_prefix} Metric: {m_name} = {m_val}")
             if node:
                 if m_name == 'execution_duration_ms':
                     node_metrics[node]['duration_ms'] = m_val
                 elif 'confidence' in m_name:
                     node_metrics[node]['confidence'] = m_val
        elif etype == "AGENT_DECISION":
            print(f"{prefix} AGENT: Decision: {data.get('message')}")
            if "fallback_node" in data: # Check if a fallback was decided
                 fallback_triggered = True
        elif etype == "AGENT_OBSERVATION":
             # Only print observations if verbose?
             # print(f"{prefix} AGENT: Observation: {data.get('message')}")
             pass
        # Add more event type handling as needed
        # else:
        #      print(f"{prefix} {etype:<15} {node if node else '---':<30} {json.dumps(data)}")

    print("-"*70)
    print(" Summary Statistics")
    print("-"*70)
    
    total_exec_time_ms = sum(m['duration_ms'] for m in node_metrics.values() if m.get('duration_ms') is not None)
    confidences = [m['confidence'] for m in node_metrics.values() if m.get('confidence') is not None]
    avg_confidence = sum(confidences) / len(confidences) if confidences else None
    errors = summary.get('error_events', [])
    
    print(f"Total Node Execution Time (sum): {total_exec_time_ms:.1f} ms" if total_exec_time_ms is not None else "N/A")
    print(f"Average Node Confidence: {avg_confidence:.3f}" if avg_confidence is not None else "N/A")
    print(f"Nodes with Errors: {len(errors)}")
    for error in errors:
        print(f"  - {error.get('node_id', '?')}: {error.get('error', 'Unknown error')}")
    print(f"Fallback Suggested/Triggered: {'Yes' if fallback_triggered else 'No'}")
    print(f"Final Graph Status: {summary.get('status', 'UNKNOWN')}")

    print("="*70)


def main():
    parser = argparse.ArgumentParser(description="View SCM execution trace logs.")
    parser.add_argument(
        "trace_file", 
        type=str, 
        help="Path to the trace log file (.jsonl) or summary file (.json)."
    )
    # Add options later for filtering, format, etc.
    
    args = parser.parse_args()
    
    trace_path = Path(args.trace_file)
    
    if not trace_path.exists():
        print(f"Error: File not found: {trace_path}", file=sys.stderr)
        sys.exit(1)
        
    summary_data = {}
    trace_events = []
    trace_id = "Unknown"

    if trace_path.suffix == '.jsonl':
        # Assume it's the event log, try to find matching summary
        trace_id = trace_path.stem.replace('trace_', '')
        summary_path = trace_path.parent / f"summary_{trace_id}.json"
        trace_events = parse_jsonl(trace_path)
        if summary_path.exists():
             try:
                 summary_data = json.loads(summary_path.read_text())
             except Exception as e:
                 print(f"Warning: Could not load summary file {summary_path}: {e}", file=sys.stderr)
                 # Try to generate basic summary from events if needed
        else:
             print(f"Warning: Summary file not found at {summary_path}. Report might be incomplete.", file=sys.stderr)
             # Attempt to get trace ID from first event if possible
             if trace_events:
                 trace_id = trace_events[0].get('trace_id', trace_id)

    elif trace_path.suffix == '.json':
        # Assume it's the summary file, try to find matching event log
        try:
            summary_data = json.loads(trace_path.read_text())
            trace_id = summary_data.get('trace_id', trace_path.stem.replace('summary_', ''))
            event_log_path = trace_path.parent / f"trace_{trace_id}.jsonl"
            if event_log_path.exists():
                 trace_events = parse_jsonl(event_log_path)
            else:
                 print(f"Warning: Event log file not found at {event_log_path}. Timeline will be empty.", file=sys.stderr)
        except Exception as e:
            print(f"Error loading summary file {trace_path}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"Error: Unknown file type '{trace_path.suffix}'. Please provide a .jsonl trace log or .json summary file.", file=sys.stderr)
        sys.exit(1)
        
    if not trace_events and not summary_data:
         print("Error: No trace data could be loaded.", file=sys.stderr)
         sys.exit(1)
         
    # Populate summary from events if summary file was missing/partial
    if not summary_data.get('start_time') and trace_events:
        for event in trace_events:
            if event.get('event_type') == 'GRAPH_START':
                summary_data['start_time'] = event.get('timestamp')
                break
    if not summary_data.get('end_time') and trace_events:
         for event in reversed(trace_events):
             if event.get('event_type') == 'GRAPH_END':
                 summary_data['end_time'] = event.get('timestamp')
                 summary_data['status'] = event.get('data', {}).get('final_status', 'UNKNOWN')
                 break
    # Could reconstruct nodes_executed, errors, agent_decisions too if needed

    print_report(trace_id, trace_events, summary_data)


if __name__ == "__main__":
    main() 