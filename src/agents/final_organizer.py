import logging
import os
import shutil
import subprocess
from pathlib import Path


logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".3gp", ".avi"}


def run_cmd(args: list[str]) -> bool:
    """Run command safely without shell interpolation."""
    try:
        subprocess.run(
            args,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.warning("Command failed: %s (%s)", args, exc)
        return False


def move_videos(source_dir: Path, target_dir: Path) -> int:
    """Move known video extensions from source directory to target directory."""
    moved = 0
    for item in source_dir.iterdir():
        if not item.is_file():
            continue
        if item.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        shutil.move(str(item), str(target_dir / item.name))
        moved += 1
    return moved


def organize() -> None:
    source_base = Path("/mnt/projects/recovered_photos")
    target_base = Path("/mnt/projects/PHOTOS_COLLECTION")
    video_dir = target_base / "VIDEOS"
    log_file = Path("/mnt/projects/RECOVERY_FINAL.log")

    video_dir.mkdir(parents=True, exist_ok=True)
    dirs = sorted(source_base.glob("photorec_out.*"))

    with log_file.open("a", encoding="utf-8") as log:
        log.write(f"Starting final organization of {len(dirs)} directories...\n")

        for directory in dirs:
            marker = directory / ".organized"
            if marker.exists():
                continue

            log.write(f"Processing {directory}...\n")
            log.flush()

            # Organize photos by EXIF dates when exiftool is available.
            run_cmd(
                [
                    "sudo",
                    "exiftool",
                    "-overwrite_original",
                    "-q",
                    "-d",
                    f"{target_base}/%Y/%m",
                    "-directory<CreateDate",
                    "-directory<DateTimeOriginal",
                    "-directory<FileModifyDate",
                    str(directory),
                    "-ext",
                    "jpg",
                    "-ext",
                    "jpeg",
                    "-ext",
                    "png",
                    "-ext",
                    "heic",
                ]
            )

            moved = move_videos(directory, video_dir)
            log.write(f"Moved videos: {moved}\n")

            # Mark as done (works without shell and without sudo).
            marker.touch(exist_ok=True)

        log.write("--- ALL DIRECTORIES PROCESSED ---\n")


if __name__ == "__main__":
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    organize()
