"""Private technical policy proposal for two pinned synthetic workbooks.

This recognizes reviewed bytes only; it grants no source rights or publication
approval. Existing repository-selection and license checks remain authoritative.
"""
import hashlib
import io
from pathlib import PurePosixPath
import stat
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED, ZIP_STORED

FIXTURES = {
    "examples/routing-ocp-server/content/examples/matrix/routing.xlsx": (
        "55ef4cbf6ce0ec0c4fbcbe381f41b24117189cbd511a7e58405102c9f52d36b0", 3379),
    "examples/routing-ocp-server/content/examples/coordinates/routing.xlsx": (
        "5f8d8ff9f87d80cff253b20661809009182cdd004af8ecc23d60bdeac6dcb930", 3095),
}
PARTS = frozenset([
    "[Content_Types].xml", "_rels/.rels", "xl/workbook.xml",
    "xl/_rels/workbook.xml.rels",
    *[f"xl/worksheets/sheet{i}.xml" for i in range(1, 6)],
])
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def validated_xml(raw):
    """Bounded structural inspection; caller separately pins complete bytes."""
    if len(raw) > 20_000:
        raise ValueError("XLSX_ARCHIVE_SIZE")
    texts = []
    try:
        with ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            names = [part.filename for part in infos]
            if len(infos) != 9 or set(names) != PARTS or len(names) != len(set(names)):
                raise ValueError("XLSX_EXACT_PART_SET_REQUIRED")
            if sum(part.file_size for part in infos) > 20_000:
                raise ValueError("XLSX_EXPANDED_SIZE")
            for part in infos:
                mode = part.external_attr >> 16
                if (part.flag_bits & 1 or stat.S_ISLNK(mode) or part.is_dir()
                        or part.file_size > 6_000
                        or part.compress_type not in {ZIP_DEFLATED, ZIP_STORED}
                        or part.file_size > max(part.compress_size, 1) * 100):
                    raise ValueError("XLSX_UNSAFE_MEMBER")
                data = archive.read(part)
                if len(data) != part.file_size:
                    raise ValueError("XLSX_MEMBER_SIZE")
                text = data.decode("utf-8", "strict")
                if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
                    raise ValueError("XLSX_XML_DECLARATION_FORBIDDEN")
                tree = ET.fromstring(text)
                for relation in tree.iter(REL_NS + "Relationship"):
                    target = relation.attrib.get("Target", "")
                    path = PurePosixPath(target)
                    if (relation.attrib.get("TargetMode") == "External" or not target
                            or ":" in target or "\\" in target
                            or path.is_absolute() or ".." in path.parts):
                        raise ValueError("XLSX_EXTERNAL_RELATIONSHIP")
                texts.append(text)
    except (BadZipFile, UnicodeError, ET.ParseError, RuntimeError) as error:
        raise ValueError("XLSX_INVALID_ARCHIVE_OR_XML") from error
    # Existing secret/personal-path scans examine all unpacked XML text.
    return "\n".join(texts)


def reviewed_fixture_text(name, raw):
    expected = FIXTURES.get(name)
    if expected is None:
        raise ValueError("XLSX_PATH_NOT_REVIEWED")
    if (len(raw) != expected[1] or hashlib.sha256(raw).hexdigest() != expected[0]):
        raise ValueError("XLSX_BYTES_NOT_REVIEWED")
    return validated_xml(raw)
