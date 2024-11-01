import os
import json
from pathlib import Path
import argparse
from PIL import Image
import subprocess
from datetime import datetime
import shutil

class ImageProcessor:
    def __init__(self, root_path: str, extensions: tuple, thumbnail_size: tuple, dry_run: bool = False):
        self.root = Path(root_path).resolve()
        self.extensions = extensions
        self.thumbnail_size = thumbnail_size
        self.dry_run = dry_run
        
        # Create thumbnails directory if it doesn't exist
        if not dry_run:
            for album in self.get_albums():
                thumb_dir = album / "thumbnails"
                thumb_dir.mkdir(exist_ok=True)
    
    def get_albums(self):
        """Get all album directories"""
        return [d for d in self.root.iterdir() if d.is_dir()]
    
    def is_valid_image(self, path: Path) -> bool:
        """Check if file is a valid image"""
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
                "thumbnail": str(Path("thumbnails") / path.name)
            }
    
    def create_thumbnail(self, image_path: Path, thumb_path: Path):
        """Create thumbnail using ImageMagick"""
        if self.dry_run:
            print(f"Would create thumbnail: {thumb_path}")
            return
        
        try:
            # Use ImageMagick to create thumbnail
            subprocess.run([
                "convert",
                str(image_path),
                "-thumbnail", f"{self.thumbnail_size[0]}x{self.thumbnail_size[1]}^",
                "-gravity", "center",
                "-extent", f"{self.thumbnail_size[0]}x{self.thumbnail_size[1]}",
                "-quality", "80",
                str(thumb_path)
            ], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error creating thumbnail for {image_path}: {e}")
            return False
        return True

    def process_images(self):
        """Process all images and generate index files"""
        # Get all albums
        albums = self.get_albums()
        
        # Create root index.json
        root_index = {
            "albums": [d.name for d in albums],
            "generated": datetime.now().isoformat()
        }
        
        if not self.dry_run:
            with open(self.root / "index.json", "w", encoding="utf-8") as f:
                json.dump(root_index, f, indent=2)
        print(f"{'Would create' if self.dry_run else 'Created'} root index.json with {len(albums)} albums")
        
        # Process each album
        for album_dir in albums:
            images_info = []
            
            # Get all valid images
            image_files = []
            for ext in self.extensions:
                image_files.extend(
                    f for f in album_dir.iterdir()
                    if f.is_file() and f.suffix.lower() in self.extensions
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
                    # Get image info
                    image_info = self.get_image_info(image_path)
                    images_info.append(image_info)
            
            # Create album index.json
            album_index = {
                "name": album_dir.name,
                "images": images_info,
                "count": len(images_info),
                "generated": datetime.now().isoformat()
            }
            
            if not self.dry_run:
                with open(album_dir / "index.json", "w", encoding="utf-8") as f:
                    json.dump(album_index, f, indent=2)
            print(f"{'Would create' if self.dry_run else 'Created'} index.json for {album_dir.name} with {len(images_info)} images")

def check_imagemagick():
    """Check if ImageMagick is installed"""
    try:
        subprocess.run(["convert", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def main():
    parser = argparse.ArgumentParser(description="Generate index.json files and thumbnails for image galleries")
    parser.add_argument("path", help="Root path of the gallery")
    parser.add_argument(
        "--extensions", 
        nargs="+", 
        default=[".jpg", ".jpeg", ".png", ".gif"],
        help="List of image extensions to include (default: .jpg .jpeg .png .gif)"
    )
    parser.add_argument(
        "--thumbnail-size",
        nargs=2,
        type=int,
        default=[300, 300],
        help="Thumbnail size in pixels (width height) (default: 300 300)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    
    args = parser.parse_args()
    
    # Check for ImageMagick
    if not check_imagemagick():
        print("Error: ImageMagick is not installed. Please install it first.")
        print("Ubuntu/Debian: sudo apt-get install imagemagick")
        print("macOS: brew install imagemagick")
        exit(1)
    
    try:
        processor = ImageProcessor(
            args.path,
            tuple(args.extensions),
            tuple(args.thumbnail_size),
            args.dry_run
        )
        processor.process_images()
        print("Processing completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    main()