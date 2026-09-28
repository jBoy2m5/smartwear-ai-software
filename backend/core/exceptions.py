"""Backend domain exceptions independent of HTTP transport."""


class BackendError(Exception):
    """Base class for expected backend failures."""


class ResourceNotFoundError(BackendError):
    """Raised when a requested domain resource does not exist."""


class ArtifactNotFoundError(ResourceNotFoundError):
    """Raised when a generated artifact is unavailable."""


class InvalidKeyFrameError(BackendError):
    """Raised when uploaded keyframe data violates backend rules."""


class UndeclaredKeyFrameError(BackendError):
    """Raised when a keyframe was not declared by the AI contract."""

