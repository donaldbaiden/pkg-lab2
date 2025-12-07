from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple
import os

from PIL import Image, UnidentifiedImageError

SUPPORTED_EXTENSIONS: Dict[str, str] = {
	".jpg": "JPEG",
	".jpeg": "JPEG",
	".png": "PNG",
	".bmp": "BMP",
	".gif": "GIF",
	".tif": "TIFF",
	".tiff": "TIFF",
	".pcx": "PCX",
}

MAX_FILES = 100_000

_MODE_DEFAULT_BITS = {
	"1": 1,
	"L": 8,
	"P": 8,
	"RGB": 8,
	"RGBA": 8,
	"CMYK": 8,
	"YCbCr": 8,
	"LAB": 8,
	"HSV": 8,
	"I": 16,
	"I;16": 16,
	"F": 32,
}

_FORMAT_COMPRESSION_HINTS = {
	"JPEG": "JPEG (lossy)",
	"PNG": "Deflate",
	"GIF": "LZW",
	"BMP": "None/RLE",
	"TIFF": "Depends on tag",
	"PCX": "RLE",
}


@dataclass(slots=True)
class ImageInfo:
	path: Path
	name: str
	format: str
	width_px: int
	height_px: int
	dpi_x: Optional[float]
	dpi_y: Optional[float]
	color_depth: str
	compression: str

	def as_dict(self) -> Dict[str, object]:
		return {
			"path": str(self.path),
			"name": self.name,
			"format": self.format,
			"width_px": self.width_px,
			"height_px": self.height_px,
			"dpi_x": self.dpi_x,
			"dpi_y": self.dpi_y,
			"color_depth": self.color_depth,
			"compression": self.compression,
		}


def scan_directory(
	directory: str, recursive: bool = True, limit: Optional[int] = None
) -> List[ImageInfo]:
	root = Path(directory).expanduser()
	if not root.exists():
		raise FileNotFoundError(directory)
	if not root.is_dir():
		raise NotADirectoryError(directory)

	target_limit = min(limit or MAX_FILES, MAX_FILES)
	result: List[ImageInfo] = []

	for path in _iter_supported_files(root, recursive):
		info = _read_image_info(path)
		if info:
			result.append(info)
		if len(result) >= target_limit:
			break

	return result


def _iter_supported_files(root: Path, recursive: bool) -> Iterator[Path]:
	stack = [root]
	while stack:
		current = stack.pop()
		try:
			with os.scandir(current) as it:
				for entry in it:
					if entry.is_symlink():
						continue
					if entry.is_dir(follow_symlinks=False) and recursive:
						stack.append(Path(entry.path))
					elif entry.is_file(follow_symlinks=False):
						ext = Path(entry.name).suffix.lower()
						if ext in SUPPORTED_EXTENSIONS:
							yield Path(entry.path)
		except PermissionError:
			continue


def _read_image_info(path: Path) -> Optional[ImageInfo]:
	try:
		with Image.open(path) as img:
			width, height = img.size
			dpi_x, dpi_y = _extract_dpi(img)
			color_depth = _describe_color_depth(img)
			compression = _detect_compression(img)

			return ImageInfo(
				path=path,
				name=path.name,
				format=(img.format or SUPPORTED_EXTENSIONS.get(path.suffix.lower(), "Unknown")),
				width_px=width,
				height_px=height,
				dpi_x=dpi_x,
				dpi_y=dpi_y,
				color_depth=color_depth,
				compression=compression,
			)
	except (UnidentifiedImageError, OSError):
		return None


def _extract_dpi(img: Image.Image) -> Tuple[Optional[float], Optional[float]]:
	info = img.info or {}
	if "dpi" in info:
		dpi = info["dpi"]
		if isinstance(dpi, tuple):
			return float(dpi[0]), float(dpi[1] if len(dpi) > 1 else dpi[0])
		return float(dpi), float(dpi)

	if "jfif_density" in info:
		x, y = info["jfif_density"]
		unit = info.get("jfif_unit", 0)
		if unit == 1:  # dots per inch
			return float(x), float(y)
		if unit == 2:  # dots per cm
			return float(x) * 2.54, float(y) * 2.54

	if "resolution" in info:
		res = info["resolution"]
		if isinstance(res, tuple):
			return float(res[0]), float(res[1] if len(res) > 1 else res[0])
		return float(res), float(res)

	return None, None


def _describe_color_depth(img: Image.Image) -> str:
	mode = img.mode or "unknown"
	bands = len(img.getbands()) or 1
	bits_per_channel = getattr(img, "bits", None)
	if bits_per_channel is None:
		bits_per_channel = _MODE_DEFAULT_BITS.get(mode, 8)
	total_bits = bits_per_channel * bands
	return f"{total_bits} бит ({mode})"


def _detect_compression(img: Image.Image) -> str:
	info = img.info or {}
	if "compression" in info:
		return str(info["compression"])
	if "compression_type" in info:
		return str(info["compression_type"])

	fmt = (img.format or "").upper()
	return _FORMAT_COMPRESSION_HINTS.get(fmt, "н/д")

