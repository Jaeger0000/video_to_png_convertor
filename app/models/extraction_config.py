from dataclasses import dataclass


@dataclass
class ExtractionConfig:
    source_video_path: str
    output_folder: str
    output_format: str
    jpeg_quality: int
    filename_prefix: str
    extraction_fps: float
    start_time_seconds: float
    end_time_seconds: float
    resolution_multiplier: float
