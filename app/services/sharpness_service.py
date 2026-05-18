import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List

import cv2
import numpy as np

from app.models.frame_data import FrameData


class SharpnessService:

    @staticmethod
    def score_image_file(file_path: str) -> float:
        img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return 0.0
        return float(cv2.Laplacian(img, cv2.CV_64F).var())

    @staticmethod
    def score_batch_parallel(
        file_paths: List[str],
        progress_callback: Callable[[int, int], None],
        cancel_flag: threading.Event,
        max_workers: int = 4,
    ) -> List[float]:
        total = len(file_paths)
        scores = [0.0] * total
        completed = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(SharpnessService.score_image_file, path): i
                for i, path in enumerate(file_paths)
            }
            for future in as_completed(future_to_idx):
                if cancel_flag.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                idx = future_to_idx[future]
                try:
                    scores[idx] = future.result()
                except Exception as e:
                    print(f"[SharpnessService] score error for index {idx}: {e}")
                    scores[idx] = 0.0
                completed += 1
                progress_callback(completed, total)

        return scores

    @staticmethod
    def select_batch_sharpest(frames: List[FrameData], batch_size: int) -> List[int]:
        selected = []
        for start in range(0, len(frames), batch_size):
            batch = frames[start: start + batch_size]
            if not batch:
                continue
            best = max(batch, key=lambda f: f.sharpness_score)
            selected.append(best.frame_index)
        return selected

    @staticmethod
    def select_top_n(frames: List[FrameData], n: int) -> List[int]:
        sorted_frames = sorted(frames, key=lambda f: f.sharpness_score, reverse=True)
        return [f.frame_index for f in sorted_frames[:n]]

    @staticmethod
    def select_top_percentage(frames: List[FrameData], percent: float) -> List[int]:
        if not frames:
            return []
        scores = [f.sharpness_score for f in frames]
        threshold = float(np.percentile(scores, 100.0 - percent))
        return [f.frame_index for f in frames if f.sharpness_score >= threshold]
