/** Photos use detection; exported QR images can also be decoded as a pure symbol. */
export async function decodeQrImage(url: string) {
  const [{ BrowserQRCodeReader }, { DecodeHintType }] = await Promise.all([
    import("@zxing/browser"),
    import("@zxing/library"),
  ]);
  const hints = new Map([[DecodeHintType.TRY_HARDER, true]]);
  try {
    return (
      await new BrowserQRCodeReader(hints).decodeFromImageUrl(url)
    ).getText();
  } catch {
    hints.set(DecodeHintType.PURE_BARCODE, true);
    return (
      await new BrowserQRCodeReader(hints).decodeFromImageUrl(url)
    ).getText();
  }
}
