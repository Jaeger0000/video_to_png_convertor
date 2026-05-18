import os
import shutil
from typing import List

from app.models.frame_data import FrameData
from app.services.video_service import VideoService


class SaveService:

    @staticmethod
    def save_selected_frames(frames: List[FrameData], output_folder: str) -> int:
        os.makedirs(output_folder, exist_ok=True)
        count = 0
        for frame in frames:
            if frame.is_selected and os.path.exists(frame.file_path):
                dest = os.path.join(output_folder, os.path.basename(frame.file_path))
                shutil.copy2(frame.file_path, dest)
                count += 1
        return count

    @staticmethod
    def save_video_clip(
        source_path: str,
        output_folder: str,
        selected_frames: List[FrameData],
    ) -> str:
        selected = [f for f in selected_frames if f.is_selected]
        if not selected:
            raise ValueError("No frames selected for clip extraction.")
        start_s = min(f.timestamp_seconds for f in selected)
        end_s = max(f.timestamp_seconds for f in selected) + 0.1
        os.makedirs(output_folder, exist_ok=True)
        base = os.path.splitext(os.path.basename(source_path))[0]
        out_path = os.path.join(output_folder, f"{base}_clip.mp4")
        VideoService.extract_clip(source_path, out_path, start_s, end_s)
        return out_path
