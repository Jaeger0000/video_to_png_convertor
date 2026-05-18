from dataclasses import dataclass


@dataclass
class VideoInfo:
    file_path: str
    file_name: str
    file_size_bytes: int
    width: int
    height: int
    fps: float
    duration_seconds: float
    total_frames: int
    codec: str
    bitrate_kbps: float
