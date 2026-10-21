"""Checks that the two domains stay separable, as decided in ADR-2."""
import ast
from pathlib import Path

DOMAINS = Path(__file__).resolve().parent.parent / "domains"


def imports_of(package):
    """Every (file, module, name) imported by the Python files of a domain package."""
    found = []
    for path in (DOMAINS / package).glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module:
                found += [(path.name, node.module, alias.name) for alias in node.names]
            elif isinstance(node, ast.Import):
                found += [(path.name, alias.name, None) for alias in node.names]
    return found


def test_sales_only_uses_labor_cost_from_personnel_and_only_in_wages_py():
    from_personnel = [(f, m, n) for f, m, n in imports_of("sales") if m.startswith("domains.personnel")]
    assert from_personnel == [("wages.py", "domains.personnel.services", "labor_cost")]


def test_personnel_never_imports_sales():
    assert not [m for _, m, _ in imports_of("personnel") if m.startswith("domains.sales")]