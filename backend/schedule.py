"""
One entry point for every schedule file: sniff the format from the content, hand the
file to its reader, return the structure the API serves. main.py (server) and the
in-browser worker both call `parse_schedule`, so the choice of reader lives here only.

Formats: P6 .xer (text starting with ERMHDR), Project XML (MSPDI: an XML document whose
root is <Project> in the schemas.microsoft.com/project namespace) and Project .mpp (an
OLE2 compound file, read through backend/mpp.py, which needs Java and is imported only
when such a file arrives).
"""

from pathlib import Path
from typing import Optional

import xml.etree.ElementTree as ET

from backend import mspdi, pmxml, xer

OLE2_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

# What the upload screen and the API accept; the content decides, the name only hints.
EXTENSIONS = (".xer", ".xml", ".mpp")

# The message for a .mpp where Java (and so MPXJ) is not available: the standalone
# build, or a server without the runtime.
MPP_NEEDS_XML = (
    "This is a Microsoft Project .mpp file, which this build cannot read. Save it from "
    "Project as XML (File > Save As > XML) and load that instead."
)


def detect_format(head: bytes) -> str:
    """'mpp', 'mspdi' or 'xer' from the first bytes of the file (an XML file is told
    apart as P6 XML or Project XML by its root element: see xml_kind). A .mpp is an OLE2
    compound file; XML is any document that starts with a declaration or an element (the
    MSPDI reader then checks the root element itself and says what it found when it is
    not MSPDI); everything else goes to the .xer reader, as every upload did before
    other formats existed, and its own message says when the file is not one."""
    if head.startswith(OLE2_SIGNATURE):
        return "mpp"
    if head.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"<"):
        return "mspdi"
    return "xer"


def xml_kind(filepath: str) -> str:
    """'pmxml' for a Primavera P6 XML export (root APIBusinessObjects), else 'mspdi'.
    Reads only up to the root element."""
    try:
        for _, el in ET.iterparse(filepath, events=("start",)):
            return "pmxml" if el.tag.rsplit("}", 1)[-1] == "APIBusinessObjects" else "mspdi"
    except ET.ParseError:
        pass
    return "mspdi"  # its reader says what is wrong with the XML


def parse_schedule(filepath: str, project_id: Optional[int] = None) -> dict:
    """Parse a schedule file of any supported format into the structure the API serves.
    Raises ValueError, with a message meant for the user, when the file is not one.
    `project_id` picks a project of a multi-project .xer (other formats hold one)."""
    path = Path(filepath)
    with path.open("rb") as fh:
        head = fh.read(4096)
    fmt = detect_format(head)
    if fmt == "mspdi":
        if xml_kind(filepath) == "pmxml":
            return pmxml.parse_pmxml(filepath, project_id)
        return mspdi.parse_mspdi(filepath)
    if fmt == "mpp":
        try:
            from backend import mpp
        except ImportError:
            raise ValueError(MPP_NEEDS_XML)
        return mspdi.parse_mspdi(mpp.to_mspdi(filepath), source_format="mpp")
    return xer.parse_xer(filepath, project_id)
