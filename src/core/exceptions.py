class NotFoundException(Exception):
    def __init__(self, message: str):
        self.message = message


class BadRequestException(Exception):
    def __init__(self, message: str):
        self.message = message


class UnauthorizedException(Exception):
    def __init__(self, message: str = "No autorizado"):
        self.message = message


class ForbiddenException(Exception):
    def __init__(self, message: str = "Acceso denegado"):
        self.message = message
