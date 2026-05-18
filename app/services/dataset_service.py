import os
import random
import shutil
import threading
from typing import Callable, Dict, List, Optional, Tuple

from app.constants import IMAGE_EXTENSIONS


def _collect_pairs(source_dir: str) -> List[Tuple[str, str]]:
    pairs = []
    for root, _, files in os.walk(source_dir):
        for fname in sorted(files):
            if os.path.splitext(fname)[1].lower() in IMAGE_EXTENSIONS:
                img = os.path.join(root, fname)
                txt = os.path.splitext(img)[0] + ".txt"
                pairs.append((img, txt))
    return pairs


def _assign_splits(
    pairs: List[Tuple[str, str]],
    mode: str,
    train_pct: float,
    val_pct: float,
    test_pct: float,
    prefix_rules: List[Dict],
    remainder_split: str,
) -> List[Tuple[str, str, str]]:
    if mode == "random":
        shuffled = list(pairs)
        random.shuffle(shuffled)
        n = len(shuffled)
        train_end = int(n * train_pct / 100)
        val_end = train_end + int(n * val_pct / 100)
        result = []
        for i, (img, txt) in enumerate(shuffled):
            if i < train_end:
                split = "train"
            elif i < val_end:
                split = "val"
            else:
                split = "test"
            result.append((img, txt, split))
        return result
    else:
        result = []
        for img, txt in pairs:
            fname = os.path.basename(img)
            matched = None
            for rule in prefix_rules:
                if fname.startswith(rule["prefix"]):
                    matched = rule["split"]
                    break
            result.append((img, txt, matched or remainder_split))
        return result


def build_dataset(
    source_dir: str,
    output_dir: str,
    name: str,
    class_names: List[str],
    split_mode: str,
    train_pct: float,
    val_pct: float,
    test_pct: float,
    prefix_rules: List[Dict],
    remainder_split: str,
    progress_cb: Optional[Callable[[int, int], None]],
    cancel_flag: threading.Event,
) -> Dict[str, int]:
    pairs = _collect_pairs(source_dir)
    if not pairs:
        raise ValueError("No image files found in source directory.")

    assignments = _assign_splits(
        pairs, split_mode, train_pct, val_pct, test_pct, prefix_rules, remainder_split
    )

    dataset_dir = os.path.join(output_dir, name)
    for split in ("train", "val", "test"):
        os.makedirs(os.path.join(dataset_dir, "images", split), exist_ok=True)
        os.makedirs(os.path.join(dataset_dir, "labels", split), exist_ok=True)

    counts: Dict[str, int] = {"train": 0, "val": 0, "test": 0}
    total = len(assignments)
    for idx, (img_path, txt_path, split) in enumerate(assignments):
        if cancel_flag.is_set():
            break
        fname = os.path.basename(img_path)
        stem = os.path.splitext(fname)[0]
        shutil.copy2(img_path, os.path.join(dataset_dir, "images", split, fname))
        if os.path.isfile(txt_path):
            shutil.copy2(txt_path, os.path.join(dataset_dir, "labels", split, stem + ".txt"))
        counts[split] += 1
        if progress_cb:
            progress_cb(idx + 1, total)

    _write_yaml(dataset_dir, class_names)
    return counts


def _write_yaml(dataset_dir: str, class_names: List[str]) -> None:
    abs_path = os.path.abspath(dataset_dir)
    names_str = "[" + ", ".join(f"'{c}'" for c in class_names) + "]"
    lines = [
        f"path: {abs_path}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        f"nc: {len(class_names)}",
        f"names: {names_str}",
    ]
    with open(os.path.join(dataset_dir, "data.yaml"), "w") as f:
        f.write("\n".join(lines) + "\n")
