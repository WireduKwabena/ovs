from .http_provider import HttpBackgroundCheckProvider
from .mock_provider import MockBackgroundCheckProvider


def default_provider_registry():
    return {
        MockBackgroundCheckProvider.key: MockBackgroundCheckProvider(),
        HttpBackgroundCheckProvider.key: HttpBackgroundCheckProvider(),
    }
