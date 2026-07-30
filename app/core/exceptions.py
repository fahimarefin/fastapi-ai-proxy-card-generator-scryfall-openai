class AppError(Exception):
    """Base class for all application-specific errors."""

    status_code: int = 500

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class CardNotFoundError(AppError):
    status_code = 404


class InvalidCardIdentifierError(AppError):
    status_code = 400


class ImageGenerationError(AppError):
    status_code = 502


class UnsupportedProviderError(AppError):
    status_code = 500
