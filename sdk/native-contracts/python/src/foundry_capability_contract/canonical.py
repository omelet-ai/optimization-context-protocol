"""Canonical JSON and digests, byte for byte the TypeScript ones.

The OCP domain servers compute ``canonicalDigest`` in TypeScript (``JSON.stringify`` of the value
with every object's keys sorted, ``shared/ocp-contracts/ocp-server-base/src/domain/canonical.ts``).
An Optimization API publishes ``catalogDigest`` from Python, and both must name the same bytes:

- object keys sorted (UTF-16 code unit order, as ``Array.prototype.sort`` on strings), except that a
  JavaScript object puts array-index keys ("0", "9", "10") first in numeric order; arrays kept;
- no whitespace; strings escaped as ``JSON.stringify`` escapes them (non-ASCII kept as is);
- numbers as JavaScript prints them: ``1.0`` is ``1``, ``1e-07`` is ``1e-7``, ``1e16`` is
  ``10000000000000000``; ``NaN`` and ``±Infinity`` are ``null``;
- ``None`` is ``null``; a value of ``undefined`` has no Python form, so nothing is dropped.

``fixtures/canonical-vectors.json`` holds vectors the TypeScript implementation wrote; the tests
hold this module to them.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from decimal import Decimal
from typing import Any

__all__ = ["canonical_json", "canonical_digest", "capability_digest", "js_number"]


def js_number(value: float | int) -> str:
    """A number as JavaScript's ``Number.prototype.toString`` prints it (what JSON.stringify uses)."""
    if isinstance(value, bool):
        raise TypeError("booleans are not numbers here")
    if isinstance(value, int):
        if abs(value) <= 2**53:
            return str(value)
        # JavaScript holds every number as a double: 2^53 + 1 is read as 2^53, 10^400 as Infinity.
        try:
            value = float(value)
        except OverflowError:
            return "null"
    if math.isnan(value) or math.isinf(value):
        return "null"
    if value == 0:
        return "0"
    # The shortest digits that round-trip, as both languages choose them.
    sign = "-" if value < 0 else ""
    digits_tuple, exponent = _shortest(abs(value))
    digits = "".join(str(d) for d in digits_tuple)
    k = len(digits)  # number of significant digits
    n = exponent + k  # the decimal point sits after n digits (ECMA-262 Number::toString)
    if k <= n <= 21:
        return sign + digits + "0" * (n - k)
    if 0 < n <= 21:
        return sign + digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return sign + "0." + "0" * (-n) + digits
    e = n - 1
    exponent_text = f"+{e}" if e >= 0 else str(e)
    if k == 1:
        return f"{sign}{digits}e{exponent_text}"
    return f"{sign}{digits[0]}.{digits[1:]}e{exponent_text}"


def _shortest(value: float) -> tuple[tuple[int, ...], int]:
    """Digits and exponent of the shortest round-trip decimal of a positive finite float."""
    decimal = Decimal(repr(value)).normalize()
    sign, digits, exponent = decimal.as_tuple()
    assert sign == 0 and isinstance(exponent, int)
    return digits, exponent


_ESCAPES = {0x08: "\\b", 0x09: "\\t", 0x0A: "\\n", 0x0C: "\\f", 0x0D: "\\r", 0x22: '\\"', 0x5C: "\\\\"}
_PLAIN = re.compile("[\x00-\x1f\"\\\\\ud800-\udfff]")


def _string(value: str) -> str:
    """A string quoted as JSON.stringify quotes it (ECMA-262 QuoteJSONString, over UTF-16 units):
    quote, backslash, \\b \\f \\n \\r \\t, other controls and lone surrogates as \\u00xx (lowercase);
    everything else, non-ASCII included, as is."""
    if _PLAIN.search(value) is None:
        return '"' + value + '"'
    units = _utf16_units(value)
    out = ['"']
    index = 0
    while index < len(units):
        unit = units[index]
        if 0xD800 <= unit <= 0xDBFF and index + 1 < len(units) and 0xDC00 <= units[index + 1] <= 0xDFFF:
            out.append(chr(0x10000 + ((unit - 0xD800) << 10) + (units[index + 1] - 0xDC00)))
            index += 2
            continue
        if unit in _ESCAPES:
            out.append(_ESCAPES[unit])
        elif unit < 0x20 or 0xD800 <= unit <= 0xDFFF:
            out.append(f"\\u{unit:04x}")
        else:
            out.append(chr(unit))
        index += 1
    out.append('"')
    return "".join(out)


def _utf16_units(key: str) -> list[int]:
    # JavaScript compares strings by UTF-16 code units.
    encoded = key.encode("utf-16-be", "surrogatepass")
    return [int.from_bytes(encoded[i : i + 2], "big") for i in range(0, len(encoded), 2)]


_MAX_ARRAY_INDEX = 2**32 - 2


def _array_index(key: str) -> int | None:
    # A JavaScript object lists its array-index keys ("0", "9", "10", ... up to 2^32 - 2, no
    # leading zeros) first, in numeric order, whatever order they were added in.
    if key.isascii() and key.isdigit() and (key == "0" or not key.startswith("0")):
        index = int(key)
        if index <= _MAX_ARRAY_INDEX:
            return index
    return None


def _ordered_keys(obj: dict[str, Any]) -> list[str]:
    """The key order of JSON.stringify(stable(obj)): array indices numerically, then the rest sorted."""
    indices = sorted((key for key in obj if _array_index(key) is not None), key=lambda key: _array_index(key))
    names = sorted((key for key in obj if _array_index(key) is None), key=_utf16_units)
    return indices + names


def canonical_json(value: Any) -> str:
    """The canonical JSON text of a JSON-shaped value (dicts with string keys, lists, scalars)."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return js_number(value)
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(canonical_json(item) for item in value) + "]"
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise TypeError(f"object keys must be strings, not {type(key).__name__}")
        return "{" + ",".join(f"{_string(key)}:{canonical_json(value[key])}" for key in _ordered_keys(value)) + "}"
    raise TypeError(f"{type(value).__name__} is not JSON")


def canonical_digest(value: Any) -> str:
    """sha256 hex of the canonical JSON (TypeScript ``canonicalDigest``)."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def capability_digest(catalog: dict[str, Any]) -> str:
    """The digest of a capability catalog, independent of where the API runs.

    ``api.baseUrl`` is a deployment address and is left out, as TypeScript ``capabilityDigest``
    leaves it out; every other field counts.
    """
    copy = json.loads(json.dumps(catalog))
    api = copy.get("api")
    if isinstance(api, dict):
        api.pop("baseUrl", None)
    return canonical_digest(copy)
