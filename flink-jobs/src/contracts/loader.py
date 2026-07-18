import os
import pathlib

try:
    import yaml
except ImportError:
    yaml = None


def _find_contracts_dir() -> pathlib.Path:
    if env := os.environ.get("CONTRACTS_DIR"):
        return pathlib.Path(env)

    script_dir = pathlib.Path(__file__).resolve().parent
    for parent in [script_dir] + list(script_dir.parents):
        candidate = parent / "contracts" / "bronze"
        if candidate.is_dir():
            return parent / "contracts"
    raise FileNotFoundError(
        "Cannot locate contracts/ directory. "
        "Set CONTRACTS_DIR env var or run from the repo root."
    )


_CONTRACT_DIR = _find_contracts_dir()


def contract_path(layer: str, table: str) -> pathlib.Path:
    return _CONTRACT_DIR / layer / f"{table}.yaml"


def load_contract(layer: str, table: str) -> dict:
    path = contract_path(layer, table)
    if not path.exists():
        raise FileNotFoundError(f"Contract not found: {path}")
    if yaml is None:
        raise RuntimeError("PyYAML not available — install with: pip install pyyaml")
    with open(path) as f:
        return yaml.safe_load(f)


def ddl_columns(layer: str, table: str) -> str:
    contract = load_contract(layer, table)
    cols = []
    for field in contract.get("schema", []):
        name = field["name"]
        dtype = field["type"]
        cols.append(f"    {name} {dtype}")
    return ",\n".join(cols)


def partition_spec(layer: str, table: str) -> str:
    contract = load_contract(layer, table)
    parts = contract.get("partitioning", [])
    return f"PARTITIONED BY ({', '.join(parts)})" if parts else ""
