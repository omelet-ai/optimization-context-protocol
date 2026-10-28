"""The reusable contract suite every Optimization API runs against itself, and the contract's
OpenAPI document with a schema checker (both need the kit's dev dependencies: pytest-style asserts,
jsonschema)."""

from .openapi import SchemaChecker, contract_openapi, contract_openapi_path
from .suite import ContractSuite

__all__ = ["ContractSuite", "SchemaChecker", "contract_openapi", "contract_openapi_path"]
