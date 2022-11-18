class PathNotAbsolute(Exception):
    pass


class ArchiverException(Exception):
    pass


class ArchiverRunning(ArchiverException):
    pass


class ArchiverStopped(ArchiverException):
    pass
