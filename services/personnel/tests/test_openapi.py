"""The committed openapi.yaml describes the code as it is, and is a valid OpenAPI document (A2 §8a)."""
import yaml
from openapi_spec_validator import validate

from app import app
from export_openapi import OPENAPI_FILE


def committed():
    return yaml.safe_load(OPENAPI_FILE.read_text(encoding="utf-8"))


def test_openapi_yaml_matches_the_code():
    assert committed() == app.openapi(), "openapi.yaml is out of date: run python export_openapi.py and commit it"


def test_openapi_yaml_is_a_valid_openapi_document():
    validate(committed())          # raises if the document breaks the OpenAPI specification


# The only endpoints anyone can call without logging in
PUBLIC = {"/health", "/auth/login", "/auth/register"}


def test_every_endpoint_documents_its_success_answer_and_401_if_it_needs_a_token():
    for path, operations in committed()["paths"].items():
        for method, operation in operations.items():
            codes = set(operation["responses"])
            assert codes & {"200", "201", "204"}, f"{method.upper()} {path} documents no success answer"
            if path not in PUBLIC:
                assert "401" in codes, f"{method.upper()} {path} does not document 401"
