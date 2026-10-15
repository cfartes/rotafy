import binascii

import pytest
from app.billing.pix import static_pix_key
from conftest import login


def payload(key="financeiro@example.com", amount=None):
    def tlv(tag, value):
        return tag + f"{len(value.encode()):02d}" + value

    account = tlv("00", "br.gov.bcb.pix") + tlv("01", key)
    value = "000201" + tlv("26", account) + "520400005303986"
    if amount is not None:
        value += tlv("54", amount)
    value += (
        "5802BR"
        + tlv("59", "NEXUS")
        + tlv("60", "BLUMENAU")
        + tlv("62", "0503***")
        + "6304"
    )
    return value + f"{binascii.crc_hqx(value.encode(), 0xFFFF):04X}"


def test_static_pix_format_amount_and_checksum():
    valid = payload()
    assert static_pix_key(valid) == "financeiro@example.com"
    for invalid in [
        valid[:-1],
        valid.replace("NEXUS", "NEXUZ"),
        "financeiro@example.com",
        payload(amount="114.00"),
    ]:
        with pytest.raises(ValueError):
            static_pix_key(invalid)


def test_pix_configuration_validated_and_legacy_save_preserves_code(client, seeded):
    login(client, email="nexus@example.com", nexus=True)
    current = client.get("/api/v1/nexus/billing/settings").json()
    data = {
        "expected_version": current["version"],
        "enabled": False,
        "pix_key": "financeiro@example.com",
        "receiver_name": "Nexus",
        "pix_copy_paste": payload(),
    }
    response = client.put("/api/v1/nexus/billing/settings", json=data)
    assert response.status_code == 200, response.text
    assert response.json()["pix_copy_paste"] == payload()
    data["expected_version"] = response.json()["version"]
    data.pop("pix_copy_paste")
    response = client.put("/api/v1/nexus/billing/settings", json=data)
    assert response.status_code == 200
    assert response.json()["pix_copy_paste"] == payload()
    data["expected_version"] = response.json()["version"]
    data["pix_key"] = "outra@example.com"
    assert client.put("/api/v1/nexus/billing/settings", json=data).status_code == 422
    data["pix_copy_paste"] = ""
    assert client.put("/api/v1/nexus/billing/settings", json=data).status_code == 200
