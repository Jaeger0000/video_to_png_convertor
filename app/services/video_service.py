import os
import threading
from typing import Callable, List, Optional

import cv2
from PIL import Image

from app.models.extraction_config import ExtractionConfig
from app.models.video_info import VideoInfo


class VideoService:

    @staticmethod
    def probe(file_path: str) -> VideoInfo:
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {file_path}")
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = (total_frames / fps) if fps > 0 else 0.0
            fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
            codec = "".join([chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)]).strip("\x00")
            file_size = os.path.getsize(file_path)
            bitrate_kbps = (file_size * 8 / 1000 / duration) if duration > 0 else 0.0
            return VideoInfo(
                file_path=file_path,
                file_name=os.path.basename(file_path),
                file_size_bytes=file_size,
                width=width,
                height=height,
                fps=fps,
                duration_seconds=duration,
                total_frames=total_frames,
                codec=codec,
                bitrate_kbps=bitrate_kbps,
            )
        finally:
            cap.release()

    @staticmethod
    def extract_frames(
        config: ExtractionConfig,
        progress_callback: Callable[[int, int], None],
        cancel_flag: threading.Event,
    ) -> List[str]:
        cap = cv2.VideoCapture(config.source_video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {config.source_video_path}")

        os.makedirs(config.output_folder, exist_ok=True)
        saved_paths: List[str] = []

        try:
            video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            start_frame = int(config.start_time_seconds * video_fps)
            end_frame = (
                int(config.end_time_seconds * video_fps)
                if config.end_time_seconds > 0
                else total_video_frames
            )
            end_frame = min(end_frame, total_video_frames)
            frame_interval = max(1, round(video_fps / config.extraction_fps))

            extract_frame_numbers = list(range(start_frame, end_frame, frame_interval))
            total_to_extract = len(extract_frame_numbers)

            if config.start_time_seconds > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

            current_pos = start_frame
            extracted_count = 0
            next_extract_idx = 0

            ext = ".jpg" if config.output_format.upper() == "JPEG" else ".png"

            while next_extract_idx < len(extract_frame_numbers):
                if cancel_flag.is_set():
                    break

                target_frame = extract_frame_numbers[next_extract_idx]

                if current_pos != target_frame:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                    current_pos = target_frame

                ret, frame_bgr = cap.read()
                if not ret:
                    next_extract_idx += 1
                    current_pos += 1
                    continue

                try:
                    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)

                    if config.resolution_multiplier != 1.0:
                        new_w = max(1, int(img.width * config.resolution_multiplier))
                        new_h = max(1, int(img.height * config.resolution_multiplier))
                        img = img.resize((new_w, new_h), Image.LANCZOS)

                    filename = f"{config.filename_prefix}_{extracted_count:06d}{ext}"
                    out_path = os.path.join(config.output_folder, filename)

                    if config.output_format.upper() == "JPEG":
                        img.save(out_path, "JPEG", quality=config.jpeg_quality)
                    else:
                        img.save(out_path, "PNG")

                    saved_paths.append(out_path)
                    extracted_count += 1
                except Exception as e:
                    print(f"[ExtractionWorker] Frame {target_frame} error: {e}")

                next_extract_idx += 1
                current_pos = target_frame + 1
                progress_callback(extracted_count, total_to_extract)

        finally:
            cap.release()

        return saved_paths

    @staticmethod
    def extract_clip(
        source_path: str,
        output_path: str,
        start_seconds: float,
        end_seconds: float,
    ) -> None:
        cap = cv2.VideoCapture(source_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {source_path}")
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            start_frame = int(start_seconds * fps)
            end_frame = int(end_seconds * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            for _ in range(end_frame - start_frame):
                ret, frame = cap.read()
                if not ret:
                    break
                writer.write(frame)
            writer.release()
        finally:
            cap.release()
