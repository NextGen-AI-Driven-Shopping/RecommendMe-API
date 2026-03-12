from fastapi import HTTPException, status

class BaseAPIException(HTTPException):
    """Base class for all custom API exceptions."""
    def __init__(self, detail: str = None, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        super().__init__(status_code=status_code, detail=detail or self.__class__.__doc__)

class AIServiceException(BaseAPIException):
    """Raised when OpenAI or Ollama fails to respond."""
    def __init__(self, detail: str = "AI service is currently unavailable"):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=detail
        )

class RateLimitException(BaseAPIException):
    """Raised when a user exceeds the 10 requests/minute limit."""
    def __init__(self, detail: str = "Rate limit exceeded. Please try again later."):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, 
            detail=detail
        )