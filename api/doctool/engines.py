"""External engines a tool may require. Detection is cheap and done per call, so installing
one (e.g. LibreOffice) is picked up without restarting the server."""
from doctool import officecore


def engine_available(name: str) -> bool:
    if name == "libreoffice":
        return officecore.find_soffice() is not None
    return False  # unknown engine names never count as available
