"""Deterministic CSV/XLSX -> API JSON with cell provenance and explicit policy."""
import csv
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_FLOOR, ROUND_CEILING
import hashlib
import io
from pathlib import PurePosixPath
import re
import xml.etree.ElementTree as ET
import zipfile
from zoneinfo import ZoneInfo

from ocp_candidate.fingerprint import fingerprint
from ocp_candidate.server_package import at, tokens, validate_request, PackageError

CONVERTER_VERSION = "0.1.0-draft.1"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


class InputError(ValueError):
    def __init__(self, code, **location):
        super().__init__(code)
        self.code, self.location = code, location


@dataclass(frozen=True)
class InputConverter:
    """Explicitly installed, trusted pure transformation; never a remote import."""
    id: str
    version: str
    convert: object


def _set(document, pointer, value):
    parts = tokens(pointer)
    if not parts:
        raise InputError("TABLE_TARGET_MUST_BE_PROPERTY")
    parent = document
    for key in parts[:-1]:
        parent = parent.setdefault(key, {})
        if not isinstance(parent, dict):
            raise InputError("MAPPING_COLLISION", pointer=pointer)
    if parts[-1] in parent:
        raise InputError("MAPPING_COLLISION", pointer=pointer)
    parent[parts[-1]] = value


def _xml(archive, name):
    raw = archive.read(name)
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise InputError("XML_DECLARATION_UNSUPPORTED", file=name)
    return ET.fromstring(raw)


def _xlsx(data, format_definition):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            names = [x.filename for x in infos]
            if len(names) != len(set(names)) or any(PurePosixPath(n).is_absolute() or ".." in PurePosixPath(n).parts for n in names):
                raise InputError("WORKBOOK_ARCHIVE_INVALID")
            if sum(x.file_size for x in infos) > format_definition.get("max_uncompressed_bytes", 50_000_000):
                raise InputError("WORKBOOK_TOO_LARGE")
            if any("vbaproject" in n.lower() or "externallinks" in n.lower() for n in names):
                raise InputError("ACTIVE_WORKBOOK_CONTENT_UNSUPPORTED")
            for name in names:
                if name.endswith(".rels"):
                    if any(e.attrib.get("TargetMode") == "External" for e in _xml(archive, name)):
                        raise InputError("EXTERNAL_WORKBOOK_LINK_UNSUPPORTED")
            workbook = _xml(archive, "xl/workbook.xml")
            relationships = _xml(archive, "xl/_rels/workbook.xml.rels")
            targets = {x.attrib["Id"]: x.attrib["Target"] for x in relationships}
            strings = []
            if "xl/sharedStrings.xml" in names:
                strings = ["".join(x.itertext()) for x in _xml(archive, "xl/sharedStrings.xml")]
            sheets = {}
            for sheet in workbook.findall("m:sheets/m:sheet", NS):
                name = sheet.attrib["name"]
                if name in sheets:
                    raise InputError("DUPLICATE_SHEET", sheet=name)
                target = targets[sheet.attrib["{" + NS["r"] + "}id"]]
                if target.startswith("/"):
                    target = target.lstrip("/")
                else:
                    target = "xl/" + target
                if ".." in PurePosixPath(target).parts:
                    raise InputError("WORKBOOK_ARCHIVE_INVALID")
                rows = []
                for row in _xml(archive, target).findall("m:sheetData/m:row", NS):
                    if len(rows) > format_definition.get("max_rows", 100000):
                        raise InputError("TOO_MANY_ROWS", sheet=name)
                    values = {}
                    for cell in row.findall("m:c", NS):
                        address = cell.attrib.get("r", "")
                        match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*)", address)
                        if not match:
                            raise InputError("CELL_ADDRESS_INVALID", sheet=name)
                        index = 0
                        for letter in match[1]:
                            index = index * 26 + ord(letter) - 64
                        if index > 16384 or index in values:
                            raise InputError("CELL_ADDRESS_INVALID", sheet=name)
                        if cell.find("m:f", NS) is not None:
                            raise InputError("FORMULA_UNSUPPORTED", sheet=name, row=int(match[2]), column=match[1])
                        node = cell.find("m:v", NS)
                        raw = node.text if node is not None and node.text is not None else ""
                        kind = cell.attrib.get("t", "n")
                        if kind == "s": raw = strings[int(raw)]
                        elif kind == "inlineStr": raw = "".join(n.text or "" for n in cell.findall(".//m:t", NS))
                        elif kind == "b": raw = "true" if raw == "1" else "false"
                        elif kind == "e": raise InputError("CELL_ERROR", sheet=name, row=int(match[2]))
                        values[index] = raw
                    if values:
                        rows.append((int(row.attrib["r"]), [values.get(i, "") for i in range(1, max(values) + 1)]))
                sheets[name] = rows
            meta_rows = sheets.pop("_ocp", [])
            if len(meta_rows) != 2 or any(len(row) != 2 for _, row in meta_rows):
                raise InputError("WORKBOOK_FORMAT_VERSION_MISMATCH")
            meta = dict((row[0], row[1]) for _, row in meta_rows)
            if meta != {"format_id": format_definition["id"], "format_version": format_definition["version"]}:
                raise InputError("WORKBOOK_FORMAT_VERSION_MISMATCH")
            return sheets
    except InputError:
        raise
    except (zipfile.BadZipFile, KeyError, ValueError, IndexError, ET.ParseError):
        raise InputError("WORKBOOK_INVALID") from None


def _convert(raw, column, location):
    actions = []
    if raw == "":
        policy = column.get("missing", "error")
        if policy == "null": return None, ["blank_to_null"], False
        if policy == "omit": return None, ["omitted"], True
        if policy == "default" and "default" in column: return column["default"], ["declared_default"], False
        raise InputError("MISSING_VALUE", **location)
    kind = column["type"]
    try:
        if kind == "string": value = raw
        elif kind == "boolean":
            if raw not in ("true", "false"): raise ValueError()
            value = raw == "true"
        elif kind in ("number", "integer"):
            value = Decimal(raw)
            if not value.is_finite(): raise ValueError()
            if "scale" in column or "offset" in column:
                value = value * Decimal(str(column.get("scale", 1))) + Decimal(str(column.get("offset", 0)))
                actions.append("declared_scale_offset")
            if "precision" in column:
                modes = {"half_even": ROUND_HALF_EVEN, "half_up": ROUND_HALF_UP, "floor": ROUND_FLOOR, "ceiling": ROUND_CEILING}
                value = value.quantize(Decimal(10) ** -column["precision"], rounding=modes[column["rounding"]])
                actions.append("declared_rounding")
            if kind == "integer" and value != value.to_integral_value(): raise ValueError()
            value = int(value) if kind == "integer" else float(value)
        elif kind == "datetime":
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if value.tzinfo is None:
                if "timezone" not in column: raise InputError("TIMEZONE_REQUIRED", **location)
                zone = ZoneInfo(column["timezone"])
                zero, one = value.replace(tzinfo=zone, fold=0), value.replace(tzinfo=zone, fold=1)
                if all(x.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != value for x in (zero, one)):
                    raise InputError("NONEXISTENT_LOCAL_TIME", **location)
                if zero.utcoffset() != one.utcoffset() and "fold" not in column:
                    raise InputError("AMBIGUOUS_LOCAL_TIME", **location)
                local = value.replace(tzinfo=zone, fold=column.get("fold", 0))
                if local.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != value:
                    raise InputError("NONEXISTENT_LOCAL_TIME", **location)
                value = local; actions.append("declared_timezone")
            value = value.astimezone(timezone.utc).isoformat(); actions.append("normalized_utc")
        elif kind == "date":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw): raise ValueError()
            value = datetime.strptime(raw, "%Y-%m-%d").date().isoformat()
        else: raise InputError("COLUMN_TYPE_UNSUPPORTED", **location)
        fingerprint(value)
    except InputError:
        raise
    except (ValueError, InvalidOperation, KeyError, OverflowError):
        raise InputError("CELL_VALUE_INVALID", **location) from None
    return value, actions, False


def _prepare_value(input_formats, payload, *, format_id=None, format_version=None, converters=None):
    """Read supplied bytes or direct JSON. This function has no execution port."""
    provenance, sources, conversion_steps = [], [], []
    if format_id is None:
        fingerprint(payload)
        value = deepcopy(payload)
        selected = None
    else:
        selected = next((f for f in input_formats if f["id"] == format_id), None)
        if selected is None or selected["version"] != format_version:
            raise InputError("INPUT_FORMAT_VERSION_UNSUPPORTED")
        converter = None
        if selected.get("converter"):
            converter = (converters or {}).get(selected["converter"])
            if not isinstance(converter, InputConverter) or not callable(converter.convert):
                raise InputError("CONVERTER_NOT_REGISTERED")
            if converter.id != selected["converter"] or converter.version != selected.get("converter_version"):
                raise InputError("CONVERTER_VERSION_MISMATCH")
        if not isinstance(payload, dict) or any(type(k) is not str for k in payload) or any(type(v) is not bytes for v in payload.values()):
            raise InputError("SUPPLIED_FILE_BYTES_REQUIRED")
        if not payload or sum(len(v) for v in payload.values()) > selected["max_bytes"]:
            raise InputError("INPUT_TOO_LARGE")
        if len({t["id"] for t in selected["tables"]}) != len(selected["tables"]):
            raise InputError("DUPLICATE_TABLE")
        expected = {t["source"] for t in selected["tables"]}
        if set(payload) != expected:
            raise InputError("INPUT_FILES_MISMATCH")
        sources = [{"file": key, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)} for key, data in sorted(payload.items())]
        workbooks = {}
        if selected["media_type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            workbooks = {name: _xlsx(data, selected) for name, data in payload.items()}
            for name, sheets in workbooks.items():
                if set(sheets) != {t["sheet"] for t in selected["tables"] if t["source"] == name}:
                    raise InputError("WORKBOOK_SHEETS_MISMATCH", file=name)
        elif selected["media_type"] != "text/csv":
            raise InputError("MEDIA_TYPE_UNSUPPORTED")
        value, parsed_tables = {}, {}
        for table in selected["tables"]:
            file, sheet = table["source"], table.get("sheet")
            if workbooks:
                rows = workbooks[file][sheet]
            else:
                try:
                    reader = csv.reader(io.StringIO(payload[file].decode(selected.get("encoding", "utf-8-sig"))), delimiter=selected.get("delimiter", ","), strict=True)
                    rows = []
                    for i, row in enumerate(reader, 1):
                        if i > selected.get("max_rows", 100000) + 1:
                            raise InputError("TOO_MANY_ROWS", file=file)
                        rows.append((i, row))
                except (UnicodeError, csv.Error, TypeError):
                    raise InputError("CSV_INVALID", file=file) from None
            if not rows: raise InputError("HEADER_REQUIRED", file=file, sheet=sheet)
            header = rows[0][1]
            columns = {c["name"]: c for c in table["columns"]}
            if len(columns) != len(table["columns"]) or len(header) != len(set(header)):
                raise InputError("DUPLICATE_COLUMN", file=file, sheet=sheet, row=rows[0][0])
            if set(header) - set(columns) or any(c["name"] not in header and c.get("required", True) for c in table["columns"]):
                raise InputError("COLUMNS_MISMATCH", file=file, sheet=sheet, row=rows[0][0])
            records, seen_ids = [], set()
            for row_number, row in rows[1:]:
                if not any(row): continue
                if len(row) > len(header) or (not workbooks and len(row) != len(header)):
                    raise InputError("ROW_WIDTH_MISMATCH", file=file, sheet=sheet, row=row_number)
                cells = dict(zip(header, row + [""] * (len(header) - len(row))))
                record = {}
                for column in table["columns"]:
                    pointer = table["target"] + ("/" + str(len(records)) if table["mode"] == "array" else "") + column["target"]
                    location = {"file": file, "sheet": sheet, "row": row_number, "column": column["name"], "pointer": pointer}
                    val, actions, omitted = _convert(cells.get(column["name"], ""), column, location)
                    if not omitted: _set(record, column["target"], val)
                    provenance.append({**location, "actions": actions})
                if table.get("key"):
                    identifier = at(record, table["key"])
                    if type(identifier) not in (str, int) or identifier in seen_ids:
                        raise InputError("DUPLICATE_OR_INVALID_ID", file=file, sheet=sheet, row=row_number, pointer=table["target"])
                    seen_ids.add(identifier)
                records.append(record)
            if table["mode"] == "object":
                if len(records) != 1: raise InputError("EXACTLY_ONE_ROW_REQUIRED", file=file, sheet=sheet)
                _set(value, table["target"], records[0])
            elif table["mode"] == "array": _set(value, table["target"], records)
            else: raise InputError("TABLE_MODE_UNSUPPORTED")
            parsed_tables[table["id"]] = (table, records)
        for table, records in parsed_tables.values():
            for relation in table.get("references", []):
                _, target_records = parsed_tables[relation["table"]]
                keys = {at(r, relation["key"]) for r in target_records}
                for index, row in enumerate(records):
                    if at(row, relation["pointer"]) not in keys:
                        pointer = table["target"] + ("/" + str(index) if table["mode"] == "array" else "") + relation["pointer"]
                        location = next(p for p in provenance if p["pointer"] == pointer)
                        raise InputError("REFERENCE_NOT_FOUND", **{k: v for k, v in location.items() if k != "actions"})
        if converter is not None:
            before = deepcopy(value)
            converted = converter.convert(deepcopy(before))
            if not isinstance(converted, dict) or set(converted) != {"input", "derivations"} or not isinstance(converted["derivations"], list):
                raise InputError("CONVERTER_RESULT_INVALID")
            value = converted["input"]
            fingerprint(value)
            for derivation in converted["derivations"]:
                if set(derivation) != {"pointer", "source_pointers", "operation"} or not isinstance(derivation["source_pointers"], list) or not derivation["operation"]:
                    raise InputError("CONVERTER_PROVENANCE_INVALID")
                at(value, derivation["pointer"])
                for pointer in derivation["source_pointers"]:
                    at(before, pointer)
            def leaves(item, pointer=""):
                if isinstance(item, dict) and item:
                    for key, child in item.items():
                        yield from leaves(child, pointer + "/" + key.replace("~", "~0").replace("/", "~1"))
                elif isinstance(item, list) and item:
                    for index, child in enumerate(item):
                        yield from leaves(child, pointer + "/" + str(index))
                else:
                    yield pointer, item
            for pointer, item in leaves(value):
                try: unchanged = fingerprint(at(before, pointer)) == fingerprint(item)
                except PackageError: unchanged = False
                if not unchanged and not any(pointer == d["pointer"] or pointer.startswith(d["pointer"] + "/") for d in converted["derivations"]):
                    raise InputError("CONVERTER_PROVENANCE_INCOMPLETE", pointer=pointer)
            conversion_steps.append({"id": converter.id, "version": converter.version,
                                     "source_fingerprint": fingerprint(before), "output_fingerprint": fingerprint(value),
                                     "derivations": deepcopy(converted["derivations"])})
    return {"value": value, "sources": sources, "provenance": provenance, "conversion_steps": conversion_steps,
            "format": {"id": selected["id"], "version": selected["version"]} if selected else None}


def prepare(descriptor, payload, *, configuration, format_id=None, format_version=None, converters=None):
    """Read supplied bytes or direct JSON for the unchanged legacy API target."""
    parsed = _prepare_value(descriptor["input_formats"], payload, format_id=format_id,
                            format_version=format_version, converters=converters)
    value = parsed.pop("value")
    try:
        effective = validate_request(descriptor, value, configuration)
    except PackageError as error:
        raise InputError(error.code, pointer=error.path) from None
    return {"input": value, "configuration": effective, "input_fingerprint": fingerprint(value),
            "configuration_fingerprint": fingerprint(effective), **parsed,
            "api": deepcopy(descriptor["api"]), "converter_version": CONVERTER_VERSION, "execute_calls": 0}
