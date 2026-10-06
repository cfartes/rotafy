"""Normalização de CPF/CNPJ com preservação de zeros e validação dos DVs."""

import re


def company_document(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = re.sub(r"[.\-/\s]", "", value).upper()
    if not re.fullmatch(r"[A-Z0-9]+", normalized):
        raise ValueError(
            "Use apenas números no CPF; no CNPJ, letras e números. Não inclua outros símbolos."
        )
    if len(normalized) == 11 and normalized.isascii() and normalized.isdigit():
        if len(set(normalized)) == 1:
            raise ValueError("CPF inválido: os dígitos verificadores não conferem.")
        for length in [9, 10]:
            check = (
                sum(int(normalized[i]) * (length + 1 - i) for i in range(length))
                * 10
                % 11
            ) % 10
            if int(normalized[length]) != check:
                raise ValueError(
                    "CPF inválido: os dígitos verificadores não conferem. Confira o documento original."
                )
    elif len(normalized) == 14:
        if (
            not re.fullmatch(r"[A-Z0-9]{12}[0-9]{2}", normalized)
            or len(set(normalized)) == 1
        ):
            raise ValueError(
                "CNPJ inválido: os dois últimos caracteres devem ser números e os dígitos verificadores devem conferir."
            )
        for length, weights in [
            (12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
            (13, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
        ]:
            remainder = (
                sum(
                    (ord(character) - 48) * weight
                    for character, weight in zip(normalized[:length], weights)
                )
                % 11
            )
            if int(normalized[length]) != (0 if remainder < 2 else 11 - remainder):
                raise ValueError(
                    "CNPJ inválido: os dígitos verificadores não conferem. Ter 14 caracteres não basta; confira o documento original."
                )
    else:
        raise ValueError("Informe CPF com 11 dígitos ou CNPJ com 14 caracteres.")
    return normalized
