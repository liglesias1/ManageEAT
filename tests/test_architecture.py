"""Checks that the two domains stay separable, as decided in ADR-2."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOMAINS = ROOT / "domains"


def imports_in(path):
    """Every (module, name) imported by one Python file."""
    found = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module:
            found += [(node.module, alias.name) for alias in node.names]
        elif isinstance(node, ast.Import):
            found += [(alias.name, None) for alias in node.names]
    return found


def imports_of(package):
    """Every (file, module, name) imported by the Python files of a domain package."""
    return [(path.name, m, n) for path in (DOMAINS / package).glob("*.py") for m, n in imports_in(path)]


def test_sales_only_uses_personnel_through_its_facade_and_only_in_wages_py():
    from_personnel = [(f, m, n) for f, m, n in imports_of("sales") if m.startswith("domains.personnel")]
    assert from_personnel == [("wages.py", "domains.personnel", "public")]


def test_personnel_never_imports_sales():
    assert not [m for _, m, _ in imports_of("personnel") if m.startswith("domains.sales")]


def test_the_overview_only_uses_the_public_facades_of_the_domains():
    from_domains = sorted((m, n) for m, n in imports_in(ROOT / "overview.py") if m.startswith("domains"))
    assert from_domains == [("domains.personnel", "public"), ("domains.sales", "public")]