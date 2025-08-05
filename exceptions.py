class TokensError(Exception):
    """Ошибка отсутствия обязательных токенов."""
    pass


class APIConnectionError(Exception):
    """Ошибка соединения с API Практикума."""
    pass


class APIStatusCodeError(Exception):
    """Ошибка неверного статус-кода от API."""
    pass
