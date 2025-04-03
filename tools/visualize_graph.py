#!/usr/bin/env python
import argparse
import json
import logging
from pathlib import Path
from collections import defaultdict
import sys
from typing import Dict, List, Optional, Tuple, Any

# Attempt to import graphviz, provide instructions if missing
try:
    import graphviz
except ImportError:
    print("Error: The 'graphviz' Python library is required. Please install it:")
    print("  pip install graphviz")
    print("Additionally, ensure the Graphviz command-line tools are installed on your system.")
    print("(e.g., 'sudo apt update && sudo apt install graphviz' on Debian/Ubuntu)")
    sys.exit(1)

# Ensure project root is discoverable for potential utils import
project_root_dir = Path(__file__).resolve().parent.parent.parent
if str(project_root_dir) not in sys.path:
     sys.path.insert(0, str(project_root_dir))
# Try importing utils, though not strictly needed for visualization itself yet
try:
     from scm.runtime.utils import load_json_file
except ImportError as e:
    # load_json_file is redefined locally, so this isn't critical if it fails
    # print(f"Warning: Could not import SCM utils ({e}). Using local definitions.")
    pass

# --- Logging Setup ---
logger = logging.getLogger("scm_visualizer")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# --- Helper Functions ---

# Local re-implementation if import fails or not desired
def load_json_file_local(file_path: Path) -> Dict[str, Any]:
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

def load_nodes_from_dir(nodes_dir: Path) -> Dict[str, Dict]:
    """Loads all valid SCM nodes from a directory."""
    nodes = {}
    if not nodes_dir.is_dir():
        logger.error(f"Nodes directory not found: {nodes_dir}")
        return nodes

    for file_path in nodes_dir.glob("*.json"):
        try:
            # Use local loader
            node_data = load_json_file_local(file_path)
            node_id = node_data.get("@id")
            if node_id:
                # Basic check for version format in ID
                if '_v' not in node_id or not node_id.rsplit('_v', 1)[-1].replace('.', '').isdigit():
                     logger.warning(f"Skipping file {file_path.name}: Node ID '{node_id}' doesn't seem to follow '_vX.Y.Z' format.")
                     continue
                nodes[node_id] = node_data
                logger.debug(f"Loaded node: {node_id}")
            else:
                 logger.warning(f"Skipping file {file_path.name}: Missing '@id'.")
        except json.JSONDecodeError:
            logger.warning(f"Skipping file {file_path.name}: Invalid JSON.")
        except Exception as e:
            logger.warning(f"Skipping file {file_path.name}: Error reading - {e}")
    logger.info(f"Loaded {len(nodes)} nodes from {nodes_dir}")
    return nodes

def load_adaptation_log(log_path: Path) -> List[Dict]:
    """Loads adaptation events from a JSONL file."""
    events = []
    if not log_path.is_file():
        logger.warning(f"Adaptation log not found at {log_path}. No adaptation edges will be drawn.")
        return events
    try:
        with open(log_path, 'r') as f:
            for i, line in enumerate(f):
                try:
                    if line.strip():
                        events.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning(f"Skipping malformed JSON on line {i+1} in {log_path.name}")
        logger.info(f"Loaded {len(events)} adaptation events from {log_path.name}")
    except Exception as e:
        logger.error(f"Error reading adaptation log {log_path.name}: {e}")
    return events

def get_node_base_id(node_id: str) -> str:
    """Extracts the base ID before the version suffix."""
    if '_v' in node_id:
        return node_id.rsplit('_v', 1)[0]
    return node_id

def get_latest_version(base_id: str, all_nodes: Dict[str, Dict]) -> Optional[str]:
    """Finds the highest version node ID for a given base ID."""
    versions = []
    for node_id in all_nodes:
        if get_node_base_id(node_id) == base_id:
            try:
                version_str = node_id.rsplit('_v', 1)[1]
                version_tuple = tuple(map(int, version_str.split('.')))
                if len(version_tuple) == 3:
                     versions.append((version_tuple, node_id))
                else:
                    logger.warning(f"Node ID '{node_id}' has unexpected version format: '{version_str}'. Skipping.")
            except (IndexError, ValueError):
                 logger.warning(f"Could not parse version from node ID: {node_id}. Skipping.")

    if not versions: return None
    versions.sort(reverse=True)
    return versions[0][1]

# --- Main Visualization Logic ---

def create_graph_viz(nodes: Dict[str, Dict], adaptations: List[Dict], output_filename: str):
    """Generates the DOT graph and renders it."""
    dot = graphviz.Digraph('SCM_Graph', comment='Sentient Computational Manifold Graph', format='png')
    dot.attr(rankdir='TB', splines='ortho', nodesep='0.8', ranksep='1.0')
    dot.attr('node', shape='record', style='filled', fillcolor='#EFEFEF', fontname='Helvetica', fontsize='10')
    dot.attr('edge', fontname='Helvetica', fontsize='9')

    nodes_by_base_id = defaultdict(list)
    for node_id, data in nodes.items():
        nodes_by_base_id[get_node_base_id(node_id)].append((node_id, data.get("version", "?.?.?")))

    latest_versions = {base: get_latest_version(base, nodes) for base in nodes_by_base_id}

    for base_id, version_list in nodes_by_base_id.items():
        use_subgraph = len(version_list) > 1
        sg = None
        graph_attr = dot

        if use_subgraph:
            with dot.subgraph(name=f'cluster_{base_id}') as sg:
                sg.attr(label=base_id.replace("node_", ""), style='filled', color='lightgrey', nodesep='0.5', ranksep='0.5')
                graph_attr = sg

        for node_id, version_str in version_list:
            node_data = nodes[node_id]
            purpose = node_data.get('purpose_statement', '')
            purpose_short = (purpose[:25] + '...') if len(purpose) > 25 else purpose
            # Create a multi-line label using HTML-like syntax for Graphviz record shape
            # Ensure inner quotes are handled correctly (e.g., using single vs double)
            label = (
                f'<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0">'
                f'<TR><TD COLSPAN="2" BGCOLOR="#CCCCCC"><B>{node_id}</B></TD></TR>'
                f'<TR><TD ALIGN="LEFT">Type:</TD><TD ALIGN="LEFT">{node_data.get("execution_logic", {}).get("type", "N/A")}</TD></TR>'
                f'<TR><TD ALIGN="LEFT">Purpose:</TD><TD ALIGN="LEFT">{purpose_short}</TD></TR>'
                f'</TABLE>>'
            )

            fillcolor = '#E8DFF5' # Default
            etype = node_data.get('execution_logic', {}).get('type', '')
            if etype == "Model_Ref": fillcolor = '#D5E8D4'
            elif etype == "External_Call": fillcolor = '#DAE8FC'
            elif etype == "Subgraph_Ref": fillcolor = '#FFE6CC'

            graph_attr.node(node_id, label=label, fillcolor=fillcolor, shape='plaintext')

    # Add dependency edges
    for node_id, node_data in nodes.items():
        base_id = get_node_base_id(node_id)
        if latest_versions.get(base_id) != node_id: continue

        for dep in node_data.get("depends_on", []):
            dep_ref = dep.get("node_ref")
            if dep_ref:
                dep_base_id = get_node_base_id(dep_ref)
                latest_dep_id = latest_versions.get(dep_base_id)
                if latest_dep_id and latest_dep_id in nodes:
                    conn_type = dep.get("connection_type", "DataFlow")
                    style = "dotted" if conn_type == "ControlFlow" else "solid"
                    dot.edge(latest_dep_id, node_id, label=conn_type, style=style, color="black")
                else:
                    logger.warning(f"Dependency target '{dep_ref}' (latest: {latest_dep_id}) not found for edge to {node_id}")

    # Add adaptation edges
    for event in adaptations:
        orig_id = event.get("original_node_id")
        new_id = event.get("new_node_id")
        trigger = event.get("adaptation_trigger", "Unknown")
        if orig_id in nodes and new_id in nodes:
            adapt_label = f"Adapted ({trigger})"
            dot.edge(orig_id, new_id, label=adapt_label, style='dashed', color='#D9534F', constraint='false', arrowhead='normal')

    # Save and render
    dot_file_path = None
    try:
        dot_file_path = Path(f"{output_filename}.gv")
        dot.save(filename=dot_file_path)
        logger.info(f"DOT graph definition saved to: {dot_file_path}")

        render_path_base = Path(output_filename)
        render_path_base.parent.mkdir(parents=True, exist_ok=True)
        rendered_file = dot.render(filename=str(render_path_base), format='png', view=False, cleanup=True)
        logger.info(f"Graph image rendered to: {rendered_file}")

    except graphviz.backend.execute.ExecutableNotFound:
         logger.error("Graphviz executable not found. Cannot render graph image.")
         logger.error("Please install Graphviz (https://graphviz.org/download/) and ensure it's in your system's PATH.")
         if dot_file_path: logger.info(f"DOT graph definition saved to: {dot_file_path} (can be rendered manually)")
    except Exception as e:
        logger.error(f"Failed to save or render graph: {e}", exc_info=True)

def main():
    parser = argparse.ArgumentParser(description="Generate a visualization of an SCM graph.")
    parser.add_argument("--nodes-dir",type=str,default="scm/nodes", help="Nodes directory.")
    parser.add_argument("--adaptation-log", type=str, default="scm_traces/adaptation_log.jsonl", help="Adaptation log path.")
    parser.add_argument("-o", "--output-file", type=str, default="scm_graph_visualization", help="Output file base name.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    args = parser.parse_args()

    if args.verbose: logging.getLogger().setLevel(logging.DEBUG)

    script_dir = Path(__file__).resolve().parent
    project_root_guess = script_dir.parent.parent

    nodes_path = Path(args.nodes_dir)
    if not nodes_path.is_absolute(): nodes_path = (project_root_guess / nodes_path).resolve()
    log_path = Path(args.adaptation_log)
    if not log_path.is_absolute(): log_path = (project_root_guess / log_path).resolve()
    output_path_base = Path(args.output_file)
    if not output_path_base.is_absolute(): output_path_base = (project_root_guess / output_path_base).resolve()

    nodes = load_nodes_from_dir(nodes_path)
    adaptations = load_adaptation_log(log_path)

    if not nodes: sys.exit(1)
    create_graph_viz(nodes, adaptations, str(output_path_base))

if __name__ == "__main__":
    main() 