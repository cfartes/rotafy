import unicodedata

PASSWORD_HELP = "Use de 8 a 128 caracteres, com pelo menos uma letra maiúscula e um caractere especial."


def validate_password(value: str) -> str:
    if not 8 <= len(value) <= 128:
        raise ValueError(PASSWORD_HELP)
    categories = [unicodedata.category(char) for char in value]
    if "Lu" not in categories or not any(
        category[0] in "PS" for category in categories
    ):
        raise ValueError(PASSWORD_HELP)
    return value
