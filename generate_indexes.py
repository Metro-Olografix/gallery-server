import os
import json
from pathlib import Path
import argparse
from PIL import Image
import subprocess
from datetime import datetime
import shutil
import hashlib


class ImageProcessor:
    def __init__(
        self,
        root_path: str,
        extensions: tuple,
        thumbnail_size: tuple,
        dry_run: bool = False,
    ):
        self.root = Path(root_path).resolve()
        self.extensions = [
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in extensions
        ]
        self.thumbnail_size = thumbnail_size
        self.dry_run = dry_run

        # Validate root path
        if not self.root.exists():
            raise ValueError(f"Root path does not exist: {self.root}")

        # Create thumbnails directory if it doesn't exist
        if not dry_run:
            for album in self.get_albums():
                thumb_dir = album / "thumbnails"
                thumb_dir.mkdir(exist_ok=True)

    def get_albums(self):
        """Get all album directories, excluding thumbnail directories"""
        return [d for d in self.root.iterdir() if d.is_dir() and d.name != "thumbnails"]

    def calculate_image_hash(self, path: Path) -> str:
        """Calculate SHA-256 hash of image file"""
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def is_valid_image(self, path: Path) -> bool:
        """Check if file is a valid image"""
        if not path.suffix.lower() in self.extensions:
            return False
        try:
            with Image.open(path) as img:
                img.verify()
            return True
        except Exception as e:
            print(f"Warning: Invalid image {path}: {e}")
            return False

    def get_image_info(self, path: Path) -> dict:
        """Get image metadata"""
        with Image.open(path) as img:
            return {
                "name": path.name,
                "width": img.width,
                "height": img.height,
                "size": path.stat().st_size,
                "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                "thumbnail": str(Path("thumbnails") / path.name),
                "hash": self.calculate_image_hash(path),
            }

    def should_update_thumbnail(self, image_path: Path, thumb_path: Path) -> bool:
        """Check if thumbnail needs to be updated"""
        if not thumb_path.exists():
            return True

        # Check if source image is newer than thumbnail
        if image_path.stat().st_mtime > thumb_path.stat().st_mtime:
            return True

        # Verify thumbnail dimensions
        try:
            with Image.open(thumb_path) as thumb:
                if thumb.size != self.thumbnail_size:
                    return True
        except Exception:
            return True

        return False

    def create_thumbnail(self, image_path: Path, thumb_path: Path) -> bool:
        """Create thumbnail using ImageMagick"""
        if self.dry_run:
            print(f"Would create thumbnail: {thumb_path}")
            return True

        if not self.should_update_thumbnail(image_path, thumb_path):
            print(f"Thumbnail up to date: {thumb_path}")
            return True

        try:
            # Use ImageMagick to create thumbnail
            subprocess.run(
                [
                    "convert",
                    str(image_path),
                    "-thumbnail",
                    f"{self.thumbnail_size[0]}x{self.thumbnail_size[1]}^",
                    "-gravity",
                    "center",
                    "-extent",
                    f"{self.thumbnail_size[0]}x{self.thumbnail_size[1]}",
                    "-quality",
                    "80",
                    str(thumb_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"Error creating thumbnail for {image_path}: {e.stderr}")
            return False
        return True

    def read_existing_index(self, path: Path) -> dict:
        """Read existing index.json if it exists"""
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Warning: Could not read existing index at {path}: {e}")
        return None

    def process_images(self):
        """Process all images and generate index files"""
        # Get all albums
        albums = self.get_albums()

        # Read existing root index
        root_index_path = self.root / "index.json"
        existing_root_index = self.read_existing_index(root_index_path)

        # Create root index.json
        root_index = {
            "albums": [d.name for d in albums],
            "generated": datetime.now().isoformat(),
            "version": "2.0",  # Added version for future compatibility
        }

        # Only write if content changed or doesn't exist
        if not self.dry_run and (
            not existing_root_index
            or existing_root_index.get("albums") != root_index["albums"]
        ):
            with open(root_index_path, "w", encoding="utf-8") as f:
                json.dump(root_index, f, indent=2)
            print(f"Created root index.json with {len(albums)} albums")
        else:
            print(f"Root index.json {'would be' if self.dry_run else 'is'} up to date")

        # Process each album
        for album_dir in albums:
            album_index_path = album_dir / "index.json"
            existing_album_index = self.read_existing_index(album_index_path)

            images_info = []
            existing_images = (
                {img["name"]: img for img in existing_album_index.get("images", [])}
                if existing_album_index
                else {}
            )

            # Get all image files
            image_files = []
            for ext in self.extensions:
                image_files.extend(
                    f
                    for f in album_dir.iterdir()
                    if f.is_file() and f.suffix.lower() == ext
                )

            # Sort images
            image_files.sort()

            # Process each image
            for image_path in image_files:
                if not self.is_valid_image(image_path):
                    continue

                # Create thumbnail
                thumb_path = album_dir / "thumbnails" / image_path.name
                if self.create_thumbnail(image_path, thumb_path):
                    # Check if image has changed
                    current_hash = self.calculate_image_hash(image_path)
                    existing_image = existing_images.get(image_path.name)

                    if existing_image and existing_image.get("hash") == current_hash:
                        images_info.append(existing_image)
                    else:
                        # Get updated image info
                        image_info = self.get_image_info(image_path)
                        images_info.append(image_info)

            # Create album index.json
            album_index = {
                "name": album_dir.name,
                "images": images_info,
                "count": len(images_info),
                "generated": datetime.now().isoformat(),
                "version": "2.0",
            }

            # Only write if content changed or doesn't exist
            if not self.dry_run and (
                not existing_album_index
                or existing_album_index.get("images") != album_index["images"]
            ):
                with open(album_index_path, "w", encoding="utf-8") as f:
                    json.dump(album_index, f, indent=2)
                print(
                    f"Created index.json for {album_dir.name} with {len(images_info)} images"
                )
            else:
                print(
                    f"Album index.json for {album_dir.name} {'would be' if self.dry_run else 'is'} up to date"
                )


def check_imagemagick():
    """Check if ImageMagick is installed and has proper permissions"""
    try:
        # Test both convert command and proper permissions
        result = subprocess.run(
            ["convert", "-version"], capture_output=True, text=True, check=True
        )
        if "ImageMagick" not in result.stdout:
            return False
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ImageMagick error: {str(e)}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Generate index.json files and thumbnails for image galleries"
    )
    parser.add_argument("path", help="Root path of the gallery")
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".jpg", ".jpeg", ".png", ".gif"],
        help="List of image extensions to include (default: .jpg .jpeg .png .gif)",
    )
    parser.add_argument(
        "--thumbnail-size",
        nargs=2,
        type=int,
        default=[300, 300],
        help="Thumbnail size in pixels (width height) (default: 300 300)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    # Check for ImageMagick
    if not check_imagemagick():
        print("Error: ImageMagick is not installed or lacks proper permissions.")
        print("Ubuntu/Debian: sudo apt-get install imagemagick")
        print("macOS: brew install imagemagick")
        print("Also ensure ImageMagick has proper permissions in policy.xml")
        exit(1)

    try:
        processor = ImageProcessor(
            args.path, tuple(args.extensions), tuple(args.thumbnail_size), args.dry_run
        )
        processor.process_images()
        print("Processing completed successfully!")

    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()
