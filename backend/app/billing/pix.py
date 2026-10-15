"""Validação local de BR Code estático, sem consulta ou integração bancária."""

import binascii
import re


def fields(raw):
    result, offset = {}, 0
    while offset < len(raw):
        header = raw[offset : offset + 4]
        if len(header) != 4 or not header.isdigit():
            raise ValueError("Pix Copia e Cola incompleto ou com formato inválido.")
        tag, length = header[:2].decode(), int(header[2:])
        offset += 4
        if offset + length > len(raw) or tag in result:
            raise ValueError("Pix Copia e Cola incompleto ou com campos repetidos.")
        result[tag] = raw[offset : offset + length]
        offset += length
    return result


def static_pix_key(value):
    raw = value.encode("utf-8")
    data = fields(raw)
    if (
        data.get("00") != b"01"
        or data.get("58") != b"BR"
        or data.get("53") != b"986"
        or not data.get("59")
        or not data.get("60")
        or not re.search(rb"6304[0-9a-fA-F]{4}$", raw)
    ):
        raise ValueError("Informe o Pix Copia e Cola completo gerado pelo banco.")
    expected = f"{binascii.crc_hqx(raw[:-4], 0xFFFF):04X}".encode()
    if data.get("63", b"").upper() != expected:
        raise ValueError(
            "O Pix Copia e Cola está incompleto ou foi alterado: verificação inválida."
        )
    if data.get("01") not in {None, b"11"} or data.get("54"):
        raise ValueError(
            "Utilize um Pix estático sem valor definido, gerado pelo banco."
        )
    for tag, content in data.items():
        if "26" <= tag <= "51":
            account = fields(content)
            if account.get("00", b"").lower() == b"br.gov.bcb.pix" and account.get(
                "01"
            ):
                return account["01"].decode("utf-8")
    raise ValueError("O código não contém uma chave Pix estática válida.")


def normalize_key(value):
    value = value.strip()
    if re.fullmatch(r"[+0-9(). /-]+", value):
        return re.sub(r"\D", "", value)
    return value.casefold()
