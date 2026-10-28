"""The contract's OpenAPI document, and checking answers against its schemas (needs jsonschema).

The document is the language-neutral source of the contract:
``shared/ocp-contracts/capability-contract/openapi/capability-contract-v1.json``. APIs in the
repository install the kit editable, so the document is found next to the kit's source;
``CAPABILITY_CONTRACT_OPENAPI`` names it otherwise.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

__all__ = ["SchemaChecker", "contract_openapi", "contract_openapi_path"]

_URI = "urn:oi-foundry:capability-contract:v1"


def contract_openapi_path() -> Path:
    override = os.environ.get("CAPABILITY_CONTRACT_OPENAPI")
    path = Path(override) if override else Path(__file__).resolve().parents[4] / "openapi" / "capability-contract-v1.json"
    if not path.is_file():
        raise FileNotFoundError(f"the Capability Contract OpenAPI document is not at {path}; install the kit editable or set CAPABILITY_CONTRACT_OPENAPI")
    return path


def contract_openapi() -> dict[str, Any]:
    return json.loads(contract_openapi_path().read_text(encoding="utf-8"))


class SchemaChecker:
    """``check(name, instance)`` asserts that an answer matches ``components.schemas[name]``."""

    def __init__(self, document: dict[str, Any] | None = None) -> None:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
        from referencing.jsonschema import DRAFT202012

        self.document = document if document is not None else contract_openapi()
        self._validator_class = Draft202012Validator
        self._registry = Registry().with_resource(_URI, Resource(contents=self.document, specification=DRAFT202012))
        self._validators: dict[str, Any] = {}

    def check(self, name: str, instance: Any) -> None:
        validator = self._validators.get(name)
        if validator is None:
            if name not in self.document["components"]["schemas"]:
                raise KeyError(f"the contract has no schema {name}")
            validator = self._validator_class(
                {"$ref": f"{_URI}#/components/schemas/{name}"}, registry=self._registry, format_checker=self._validator_class.FORMAT_CHECKER
            )
            self._validators[name] = validator
        errors = sorted(validator.iter_errors(instance), key=lambda error: [str(part) for part in error.absolute_path])
        if errors:
            details = "; ".join(f"{'/'.join(str(part) for part in error.absolute_path) or '(root)'}: {error.message}" for error in errors[:5])
            raise AssertionError(f"the answer does not match {name}: {details}")
