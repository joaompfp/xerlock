"""
Microsoft Project .mpp files (Project 98 to current), server only: MPXJ reads the file
and writes it back as MSPDI XML in memory, and backend/mspdi.py reads that. Nothing is
written to disk here and nothing is kept: the bytes live for the request.

MPXJ is a Java library (LGPL-2.1); the mpxj package on PyPI bundles its jars and JPype
bridges the JVM. The JVM is started once per process, on the first .mpp, so the
standalone build and the plain tests never need Java: backend/schedule.py imports this
module only when a .mpp arrives, and an ImportError there means "save it as XML".
"""

import threading

import jpype  # noqa: F401  (ImportError here is the signal schedule.py relies on)
import mpxj  # noqa: F401  (adds the MPXJ jars to the JVM class path)

_lock = threading.Lock()


def _jvm():
    """Start the JVM once; later callers find it running. JPype needs a JRE on the
    machine (JAVA_HOME, or java on PATH)."""
    with _lock:
        if not jpype.isJVMStarted():
            # No JIT warm-up tricks: a conversion is a few seconds at most. JPype
            # attaches any Python thread that calls into Java, so the server's thread
            # pool needs nothing more.
            jpype.startJVM(convertStrings=True)


def to_mspdi(filepath: str) -> bytes:
    """The .mpp as MSPDI XML bytes, exactly what Project's File > Save As > XML would
    give for the same data as far as MPXJ can tell. Raises ValueError, with a message
    for the user, when MPXJ cannot read the file (a password, a corrupt file)."""
    _jvm()
    from java.io import ByteArrayOutputStream
    from org.mpxj.mspdi import MSPDIWriter
    from org.mpxj.reader import UniversalProjectReader

    try:
        project = UniversalProjectReader().read(filepath)
    except jpype.JException as e:  # org.mpxj.MPXJException and friends
        raise ValueError(f"MPXJ could not read this .mpp file: {e.getMessage()}")
    if project is None:
        raise ValueError("MPXJ did not recognise this file as a Microsoft Project file.")
    out = ByteArrayOutputStream()
    writer = MSPDIWriter()
    # Timephased data is per-assignment, per-period work: large and not used.
    writer.setWriteTimephasedData(False)
    writer.write(project, out)
    return bytes(out.toByteArray())
