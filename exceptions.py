class TokensError(Exception):
    """Ошибка отсутствия обязательных токенов."""
    pass


class APIStatusCodeError(Exception):
    """Ошибка неверного статус-кода от API."""
    pass
