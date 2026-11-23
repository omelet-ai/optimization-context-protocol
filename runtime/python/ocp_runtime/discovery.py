"""Progressive, offline discovery for arbitrary server-package API schemas.

Every technical value is projected from the descriptor. Localized prose is data,
and connector credentials or runtime configuration are never inputs to discovery.
"""
import base64
from copy import deepcopy
import json
from ocp_candidate.fingerprint import fingerprint
from ocp_candidate.server_package import lint_package, PackageError


class Discovery:
    def __init__(self, descriptor, *, descriptor_schema=None, operation_service=None):
        lint_package(descriptor, descriptor_schema=descriptor_schema, supported_extensions=("ocp.operations",))
        if "ocp.operations" in descriptor["required_extensions"] and operation_service is None:
            raise PackageError("REQUIRED_OPERATION_SERVICE_MISSING")
        self.document = deepcopy(descriptor)
        self.digest = fingerprint(self.document)
        d = self.document
        self.sections = {
            "api": [{"id": "contract", "value": d["api"]}, {"id": "profile", "value": d["profile"]}],
            "input": [{"id": kind, "value": d["schemas"][d["api"][kind + "_schema"]]}
                      for kind in ("input", "configuration", "result")]
                     + [{"id": "defaults", "value": d["configuration_defaults"]},
                        {"id": "configuration_rules", "value": d["configuration_rules"]}],
            "objectives": [{"id": i["id"], "value": i} for i in d["capabilities"]["objectives"]],
            "constraints": [{"id": i["id"], "value": i} for i in d["capabilities"]["constraints"]],
            "metrics": [{"id": i["id"], "value": i} for i in d["metrics"]],
            "input_formats": [{"id": i["id"], "value": i} for i in d["input_formats"]],
            "bindings": [{"id": i["id"], "value": i} for i in d["bindings"]],
            "playbooks": [{"id": i["id"], "value": i} for i in d["playbooks"]],
            "interpretation": [
                {"id": "units", "value": d["units"]},
                {"id": "execution", "scope": "optimization_api",
                 "description": "These are the underlying optimization API's execution capabilities. "
                     "They do not describe the MCP binding's asynchronous jobs, persisted job records "
                     "or local worker cancellation; inspect ocp_context.binding for those capabilities.",
                 "value": d["capabilities"]["execution"]},
                {"id": "solution_states", "value": {
                    "optimal": "Engine reports an optimum with its proof method; an independent checker may have narrower scope.",
                    "feasible": "A solution was returned; inspect the evaluation report and its unverified items.",
                    "infeasible": "Engine reports proven infeasibility, not a timeout or failed search.",
                    "unknown": "No feasible or optimal solution is certified; infeasibility has not been proved. An explicitly labelled candidate or diagnostics may be returned; do not rank it as a feasible solution."}}]}
        self.operation_service = operation_service
        if operation_service is not None:
            if operation_service.descriptor != self.document:
                raise PackageError("OPERATION_DISCOVERY_CONTRACT_MISMATCH")
            declared = operation_service.advertised()
            self.sections["operations"] = [{"id": value["id"], "value": value} for value in declared]
            refs = sorted({value[key] for value in declared for key in ("request_schema", "response_schema", "context_schema") if key in value})
            self.sections["operation_schemas"] = [{"id": ref, "value": deepcopy(d["schemas"][ref])} for ref in refs]

    def _locale(self, requested):
        served = requested if requested in self.document["localizations"] else self.document["default_locale"]
        return {"requested": requested, "served": served, "fallback": served != requested}

    def summary(self, *, locale="en"):
        if self.operation_service is not None: self.operation_service.advertised()
        language = self._locale(locale)
        return {"id": self.document["id"], "version": self.document["version"], "digest": deepcopy(self.digest),
                "profile": deepcopy(self.document["profile"]), "locale": language,
                "text": deepcopy(self.document["localizations"][language["served"]]),
                "sections": [{"id": k, "count": len(v)} for k, v in self.sections.items()],
                "complete": True, "scope": "summary", "execute_calls": 0}

    def _check_digest(self, expected):
        if self.operation_service is not None: self.operation_service.advertised()
        if expected != self.digest:
            raise PackageError("DISCOVERY_CHANGED")

    def section(self, section, *, expected_digest, locale="en", limit=10, cursor=None, max_bytes=65536):
        self._check_digest(expected_digest)
        if section not in self.sections:
            raise PackageError("SECTION_NOT_FOUND")
        if type(limit) is not int or not 1 <= limit <= 100 or type(max_bytes) is not int or not 1024 <= max_bytes <= 1048576:
            raise PackageError("INVALID_PAGE_LIMIT")
        offset = 0
        if cursor is not None:
            try:
                if not isinstance(cursor, str) or len(cursor) > 2048:
                    raise ValueError()
                token = json.loads(base64.urlsafe_b64decode(cursor.encode()))
                if set(token) != {"digest", "section", "locale", "offset"} or token["digest"] != self.digest or token["section"] != section or token["locale"] != locale:
                    raise ValueError()
                offset = token["offset"]
                if type(offset) is not int or not 0 < offset < len(self.sections[section]):
                    raise ValueError()
            except (ValueError, TypeError, KeyError, UnicodeError):
                raise PackageError("CURSOR_INVALID_OR_STALE") from None
        items = deepcopy(self.sections[section][offset:offset + limit])
        # Never truncate a schema or item. Ask the caller to use an item request.
        if len(json.dumps(items, ensure_ascii=False).encode()) > max_bytes:
            raise PackageError("SECTION_TOO_LARGE_USE_ITEM")
        next_offset = offset + len(items)
        next_cursor = None
        if next_offset < len(self.sections[section]):
            next_cursor = base64.urlsafe_b64encode(json.dumps({"digest": deepcopy(self.digest), "section": section, "locale": locale, "offset": next_offset}, sort_keys=True).encode()).decode()
        return {"section": section, "digest": deepcopy(self.digest), "locale": self._locale(locale), "items": items,
                "complete": next_cursor is None, "next_cursor": next_cursor, "execute_calls": 0}

    def item(self, section, item_id, *, expected_digest, locale="en"):
        self._check_digest(expected_digest)
        found = next((i for i in self.sections.get(section, []) if i["id"] == item_id), None)
        if found is None:
            raise PackageError("ITEM_NOT_FOUND")
        return {"section": section, "digest": deepcopy(self.digest), "locale": self._locale(locale),
                "item": deepcopy(found), "complete": True, "execute_calls": 0}

    def support(self, capability_id):
        for kind in ("objectives", "constraints"):
            found = next((v for v in self.document["capabilities"][kind] if v["id"] == capability_id), None)
            if found:
                return {"status": "declared", "kind": kind, "capability": deepcopy(found),
                        "conditions": deepcopy(self.document["configuration_rules"]),
                        "required_input_schema": deepcopy(self.document["schemas"][self.document["api"]["input_schema"]]),
                        "digest": deepcopy(self.digest)}
        return {"status": "not_advertised", "id": capability_id, "action": "Do not submit it; ask the server author for a supported profile.", "digest": deepcopy(self.digest)}
