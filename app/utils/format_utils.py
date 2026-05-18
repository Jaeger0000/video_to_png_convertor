def bytes_to_human(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def kbps_to_human(kbps: float) -> str:
    if kbps >= 1000:
        return f"{kbps / 1000:.2f} Mbps"
    return f"{kbps:.0f} kbps"
