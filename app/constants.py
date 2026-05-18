import os
from enum import Enum, auto

APP_NAME = "Video Frame Extractor"
APP_VERSION = "1.0.0"

DEFAULT_JPEG_QUALITY = 85
DEFAULT_EXTRACTION_FPS = 1.0
DEFAULT_FILENAME_PREFIX = "frame"
DEFAULT_RESOLUTION_MULTIPLIER = 1.0
THUMBNAIL_PAGE_SIZE = 100
THUMBNAIL_SIZE_PX = 160
CHART_MAX_POINTS = 2000
DEFAULT_CPU_WORKERS = max(1, (os.cpu_count() or 2) - 1)


class FilterMode(Enum):
    ALL = auto()
    SELECTED = auto()
    UNSELECTED = auto()
    SHARPNESS_DESC = auto()
    SHARPNESS_ASC = auto()


class SelectionMode(Enum):
    BATCH = auto()
    BEST_N = auto()
    TOP_PERCENT = auto()
    MANUAL = auto()


IMAGE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp",
})

VIDEO_EXTENSIONS = frozenset({
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv",
    ".3gp", ".m4v", ".mpg", ".mpeg", ".ts", ".mts", ".m2ts",
    ".vob", ".ogv", ".rm", ".rmvb", ".asf", ".divx", ".f4v",
    ".h264", ".h265", ".hevc", ".264", ".265", ".dv", ".mod",
    ".tod", ".mxf", ".roq", ".nsv", ".xvid", ".tp", ".trp",
    ".evo", ".bik", ".smk", ".amv", ".dpg", ".drc",
    ".yuv", ".svi", ".flc", ".fli", ".mpe", ".qt", ".wm",
    ".wmx", ".wvx", ".ram", ".ra", ".rv", ".ivf", ".3g2",
    ".f4p", ".f4a", ".f4b", ".ogm", ".ogx", ".mp2", ".m2v",
})
