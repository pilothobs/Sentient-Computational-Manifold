import json
import sys
from jsonschema import validate, ValidationError
from pathlib import Path
from rich import print

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas/scm_node.schema.json"


def load_json(file_path):
    with open(file_path, "r") as f:
        return json.load(f)


def validate_node(node_path):
    try:
        schema = load_json(SCHEMA_PATH)
        node = load_json(node_path)
        validate(instance=node, schema=schema)
        print(f"[green]✔ Node '{node_path}' is valid.[/green]")
    except ValidationError as ve:
        print(f"[red]✖ Validation error in '{node_path}': {ve.message}[/red]")
    except Exception as e:
        print(f"[red]✖ Unexpected error: {e}[/red]")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("[yellow]Usage: python validate_node.py path/to/node.json[/yellow]")
    else:
        validate_node(Path(sys.argv[1])) 