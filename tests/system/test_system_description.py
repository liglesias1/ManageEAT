"""system.yaml and the OpenAPI documents are valid and say what the code does (A2 §8a).

The JSON Schema only checks the format of system.yaml. These tests also check it is true, so the file cannot
drift from the code:

- every environment variable a service reads in its config.py is listed, with the same default, and nothing
  else is listed; secrets (no default in the code) are marked secret;
- every endpoint one service calls exists in the other's openapi.yaml, and the fields the caller reads are in
  the documented answer;
- the services are the ones in docker-compose.yml, and every path it names exists.

    pip install -r tests/system/requirements.txt
    python -m pytest tests/system -v
"""
import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate as validate_openapi

ROOT = Path(__file__).resolve().parents[2]
SYSTEM = yaml.safe_load((ROOT / "system.yaml").read_text(encoding="utf-8"))
SCHEMA = json.loads((ROOT / "system.schema.json").read_text(encoding="utf-8"))
SERVICES = SYSTEM["services"]

# os.getenv("NAME") or os.getenv("NAME", "default") in a config.py
GETENV = re.compile(r'os\.getenv\(\s*"([A-Z][A-Z0-9_]*)"\s*(?:,\s*"([^"]*)"\s*)?\)')

# What each caller reads from the answer of the endpoint it calls (domain/wages.py and domain/demand.py)
FIELDS_READ = {
    "GET /personnel/labor-cost": {"labor_cost"},
    "GET /sales/covers": {"covers", "open_days"},
}


def openapi(service):
    return yaml.safe_load((ROOT / SERVICES[service]["openapi"]).read_text(encoding="utf-8"))


def variables_in_code(service):
    """{name: default or None} for every variable the service's config.py reads."""
    source = (ROOT / SERVICES[service]["path"] / "config.py").read_text(encoding="utf-8")
    return {name: default or None for name, default in GETENV.findall(source)}


def answer_schema(document, method, path):
    """The JSON schema of the success answer of an operation, with a top-level $ref resolved."""
    operation = document["paths"][path][method.lower()]
    answer = next(operation["responses"][code] for code in ("200", "201") if code in operation["responses"])
    schema = answer["content"]["application/json"]["schema"]
    if "$ref" in schema:
        schema = document["components"]["schemas"][schema["$ref"].split("/")[-1]]
    return schema


# ---------- Format ----------

def test_system_yaml_follows_the_provided_schema():
    Draft202012Validator.check_schema(SCHEMA)
    errors = sorted(Draft202012Validator(SCHEMA).iter_errors(SYSTEM), key=lambda e: list(e.path))
    assert not errors, "\n".join(f"{'/'.join(map(str, e.path))}: {e.message}" for e in errors)


def test_system_yaml_points_editors_at_the_schema():
    first_line = (ROOT / "system.yaml").read_text(encoding="utf-8").splitlines()[0]
    assert first_line == "# yaml-language-server: $schema=./system.schema.json"


@pytest.mark.parametrize("service", sorted(SERVICES))
def test_each_openapi_yaml_is_a_valid_openapi_document(service):
    validate_openapi(openapi(service))


# ---------- True to the code ----------

@pytest.mark.parametrize("service", sorted(SERVICES))
def test_every_variable_the_code_reads_is_listed_with_its_default(service):
    in_code = variables_in_code(service)
    listed = SERVICES[service]["env"]
    assert set(listed) == set(in_code), f"{service}: listed {sorted(listed)} but config.py reads {sorted(in_code)}"
    for name, default in in_code.items():
        if default is None:
            assert listed[name].get("secret") is True, f"{service}: {name} has no default, so it must be a secret"
        else:
            assert str(listed[name]["default"]) == default, f"{service}: {name} defaults to {default!r} in the code"


@pytest.mark.parametrize("service", sorted(SERVICES))
def test_port_default_and_health_match_the_service(service):
    description = SERVICES[service]
    assert str(description["port_default"]) == variables_in_code(service)["PORT"]
    assert description.get("health", "/health") in openapi(service)["paths"]


@pytest.mark.parametrize("service", sorted(SERVICES))
def test_calls_match_the_other_services_openapi_and_config(service):
    env = variables_in_code(service)
    for call in SERVICES[service].get("calls", []):
        assert call["service"] in SERVICES and call["service"] != service
        assert call["url_env"] in env, f"{service} does not read {call['url_env']}"
        timeout_env = call["url_env"].replace("_URL", "_TIMEOUT_S")
        assert float(env[timeout_env]) == call["timeout_s"], f"{service}: timeout_s differs from {timeout_env}"
        called = openapi(call["service"])
        for endpoint in call["endpoints"]:
            method, path = endpoint.split(" ", 1)
            assert method.lower() in called["paths"].get(path, {}), \
                f"{endpoint} is not in {call['service']}'s openapi.yaml"
            documented = set(answer_schema(called, method, path).get("properties", {}))
            missing = FIELDS_READ.get(endpoint, set()) - documented
            assert not missing, f"{endpoint}: {service} reads {sorted(missing)}, which the answer does not document"


def test_the_services_are_the_ones_in_docker_compose():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))["services"]
    for name, description in SERVICES.items():
        assert name in compose, f"{name} is not a service in docker-compose.yml"
        assert compose[name]["build"]["context"].rstrip("/") == description["path"].rstrip("/")


def test_every_path_it_names_exists():
    assert (ROOT / SYSTEM["ui"]["path"]).is_dir()
    assert set(SYSTEM["ui"]["calls"]) == set(SERVICES)
    for description in SERVICES.values():
        for key in ("path", "openapi", "migrations"):
            assert (ROOT / description[key]).exists(), f"{description[key]} does not exist"


def test_azure_names_start_with_the_prefix():
    prefix = SYSTEM["prefix"]
    assert prefix == SYSTEM["student"].replace(".", "-")
    assert SYSTEM["ui"]["storage_account"].startswith(prefix.replace("-", ""))
    assert SYSTEM["azure"]["resource_group"] == f"rg-{prefix}"
    for name in (SYSTEM["azure"]["container_apps_environment"], SYSTEM["azure"]["sql_server"],
                 *[d["azure"][key] for d in SERVICES.values() for key in ("container_app", "sql_database")]):
        assert name.startswith(prefix), f"{name} does not start with {prefix}"