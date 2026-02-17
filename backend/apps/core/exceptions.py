from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """Project-wide DRF exception handler wrapper."""
    return exception_handler(exc, context)
