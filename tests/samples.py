"""Minimal byte signatures of image formats for upload tests."""

PAD = b"\x00" * 600

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + PAD
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + PAD
GIF = b"GIF89a" + PAD
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + PAD
HEIC = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + PAD
HEIF = b"\x00\x00\x00\x18ftypmif1\x00\x00\x00\x00mif1heix" + PAD
AVIF = b"\x00\x00\x00\x1cftypavif\x00\x00\x00\x00avifmif1miaf" + PAD
TEXT = b"just some text, not an image\n" * 20
PDF = b"%PDF-1.7\n" + PAD
