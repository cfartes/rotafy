// Documentos sintéticos distintos por execução, com dígitos verificadores válidos.
export function testDocument() {
  let value = String(Date.now()).slice(-9);
  for (const length of [9, 10]) {
    const remainder =
      [...value].reduce(
        (sum, digit, i) => sum + Number(digit) * (length + 1 - i),
        0,
      ) % 11;
    value += remainder < 2 ? "0" : String(11 - remainder);
  }
  return value;
}
