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

from backend import mspdi, xer

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
    """'mpp', 'mspdi' or 'xer' from the first bytes of the file. A .mpp is an OLE2
    compound file; XML is any document that starts with a declaration or an element (the
    MSPDI reader then checks the root element itself and says what it found when it is
    not MSPDI); everything else goes to the .xer reader, as every upload did before
    other formats existed, and its own message says when the file is not one."""
    if head.startswith(OLE2_SIGNATURE):
        return "mpp"
    if head.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"<"):
        return "mspdi"
    return "xer"


def parse_schedule(filepath: str) -> dict:
    """Parse a schedule file of any supported format into the structure the API serves.
    Raises ValueError, with a message meant for the user, when the file is not one."""
    path = Path(filepath)
    with path.open("rb") as fh:
        head = fh.read(4096)
    fmt = detect_format(head)
    if fmt == "mspdi":
        return mspdi.parse_mspdi(filepath)
    if fmt == "mpp":
        try:
            from backend import mpp
        except ImportError:
            raise ValueError(MPP_NEEDS_XML)
        return mspdi.parse_mspdi(mpp.to_mspdi(filepath), source_format="mpp")
    return xer.parse_xer(filepath)
