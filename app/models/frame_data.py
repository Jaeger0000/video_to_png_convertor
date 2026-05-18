from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FrameData:
    frame_index: int
    source_frame_number: int
    timestamp_seconds: float
    file_path: str
    sharpness_score: float = 0.0
    is_selected: bool = True
    thumbnail: Optional[object] = field(default=None, repr=False)
