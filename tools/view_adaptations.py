#!/usr/bin/env python
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
import sys

def format_timestamp(iso_str):
    """Formats ISO timestamp for display.""" 
    if not iso_str: return "N/A"
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S") # Simpler format for this viewer
    except (ValueError, TypeError):
        return iso_str

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
        print(f"Error: Adaptation log file not found: {file_path}", file=sys.stderr)
        return []
    except Exception as e:
         print(f"Error reading adaptation log file {file_path}: {e}", file=sys.stderr)
         return []
    return events

def print_adaptation_report(log_path: Path, events: list):
    """Prints a summary of adaptation events."""
    print("="*70)
    print(f" SCM Node Adaptation Log Report")
    print("="*70)
    print(f"Log File: {log_path}")
    print(f"Total Adaptations Logged: {len(events)}")
    print("-"*70)
    
    if not events:
        print("No adaptation events found.")
        print("="*70)
        return
        
    # Sort by adaptation timestamp
    events.sort(key=lambda x: x.get('adaptation_timestamp', ''))

    for i, event in enumerate(events):
        print(f"Event {i+1}: Adaptation of '{event.get('original_node_id')}'")
        print(f"  Timestamp:   {format_timestamp(event.get('adaptation_timestamp'))}")
        print(f"  Agent:       {event.get('adapting_agent')}")
        print(f"  Trigger:     {event.get('adaptation_trigger')}")
        if event.get('trigger_details'):
            print(f"  Trigger Details: {json.dumps(event['trigger_details'])}")
        print(f"  Method:      {event.get('adaptation_method')}")
        if event.get('method_params'):
             print(f"  Method Params: {json.dumps(event['method_params'])}")
        print(f"  Old Version: {event.get('original_version')}")
        print(f"  New Version: {event.get('new_version')} (Node ID: '{event.get('new_node_id')}')")
        print(f"  Rationale:   {event.get('rationale')}")
        print("-"*70)

def main():
    parser = argparse.ArgumentParser(description="View SCM node adaptation logs.")
    parser.add_argument(
        "log_file", 
        type=str, 
        nargs='?', # Optional, defaults
        default="./adaptation_log.jsonl",
        help="Path to the adaptation log file (.jsonl). Default: ./adaptation_log.jsonl"
    )
    
    args = parser.parse_args()
    
    log_path = Path(args.log_file)
    
    # Resolve path relative to project root if needed
    if not log_path.is_absolute():
        script_dir = Path(__file__).resolve().parent # .../scm-env/scm/tools
        project_root_guess = script_dir.parent.parent # .../scm-env/
        resolved_path = project_root_guess / log_path
        print(f"Attempting to read log from: {resolved_path}", file=sys.stderr)
        log_path = resolved_path

    events = parse_jsonl(log_path)
    
    if not events and not log_path.exists():
         # If default path used and doesn't exist, exit quietly maybe?
         if args.log_file == "./adaptation_log.jsonl":
              print(f"Default adaptation log file not found at {log_path}. No report generated.", file=sys.stderr)
              sys.exit(0) 
         else: # If user specified a non-existent file
             sys.exit(1)
             
    print_adaptation_report(log_path, events)

if __name__ == "__main__":
    main() 