"""Minimal byte signatures of image formats for upload tests."""

PAD = b"\x00" * 600

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + PAD
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + PAD
GIF = b"GIF89a" + PAD
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + PAD
HEIC = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + PAD
HEIF = b"\x00\x00\x00\x18ftypmif1\x00\x00\x00\x00mif1heix" + PAD
AVIF = b"\x00\x00\x00\x1cftypavif\x00\x00\x00\x00avifmif1miaf" + PAD
MOV = b"\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00qt  " + PAD
MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42" + PAD
M4V = b"\x00\x00\x00\x1cftypM4V \x00\x00\x00\x01M4V M4A mp42isom" + PAD
MKV = b"\x1aE\xdf\xa3\x93B\x82\x88matroska" + PAD
TEXT = b"just some text, not an image\n" * 20
PDF = b"%PDF-1.7\n" + PAD
