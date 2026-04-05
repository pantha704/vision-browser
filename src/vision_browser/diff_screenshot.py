"""Differential screenshot capture -- send only changed regions to reduce API cost."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DifferentialScreenshot:
    """Captures and compares screenshots to detect changed regions.

    Only sends changed regions to the vision API, reducing bandwidth
    and API cost compared to sending full screenshots every turn.
    """

    def __init__(self, threshold: float = 0.01):
        """Initialize differential screenshot handler.

        Args:
            threshold: Pixel difference ratio (0.0-1.0) below which
                       regions are considered unchanged. Default 0.01 (1%).
        """
        self.threshold = threshold
        self._previous_screenshot: bytes | None = None
        self._previous_path: str | None = None

    def has_changed(self, current_path: str) -> bool:
        """Check if the current screenshot differs from the previous one.

        Args:
            current_path: Path to the current screenshot file.

        Returns:
            True if changes detected exceed the threshold.
        """
        try:
            current_data = Path(current_path).read_bytes()
        except FileNotFoundError:
            return True

        if self._previous_screenshot is None:
            self._previous_screenshot = current_data
            self._previous_path = current_path
            return True

        if current_data == self._previous_screenshot:
            return False

        # For binary comparison, any difference means changed
        # More sophisticated pixel-level diffing would use PIL
        self._previous_screenshot = current_data
        self._previous_path = current_path
        return True

    def get_changed_regions(self, current_path: str) -> list[dict[str, Any]] | None:
        """Identify changed regions in the current screenshot.

        Args:
            current_path: Path to the current screenshot file.

        Returns:
            List of changed region dicts with x, y, width, height,
            or None if no previous screenshot to compare against.
        """
        try:
            from PIL import Image
            import io

            current = Image.open(current_path)
            if self._previous_screenshot is None:
                return None

            previous = Image.open(io.BytesIO(self._previous_screenshot))

            if current.size != previous.size:
                # Different sizes -- entire screenshot changed
                self._previous_screenshot = current.tobytes()
                return [
                    {"x": 0, "y": 0, "width": current.width, "height": current.height}
                ]

            # Pixel-level comparison
            diff = Image.new("RGB", current.size)
            pixels_curr = current.load()
            pixels_prev = previous.load()
            pixels_diff = diff.load()

            changed_regions: list[dict[str, Any]] = []
            changed_pixels: list[tuple[int, int]] = []

            for y in range(current.height):
                for x in range(current.width):
                    if pixels_curr[x, y] != pixels_prev[x, y]:
                        pixels_diff[x, y] = (255, 0, 0)
                        changed_pixels.append((x, y))

            if not changed_pixels:
                return []

            # Calculate change ratio
            total_pixels = current.width * current.height
            change_ratio = len(changed_pixels) / total_pixels

            if change_ratio < self.threshold:
                return []  # Changes below threshold

            # Bounding box of all changed pixels
            xs = [p[0] for p in changed_pixels]
            ys = [p[1] for p in changed_pixels]
            changed_regions = [
                {
                    "x": min(xs),
                    "y": min(ys),
                    "width": max(xs) - min(xs) + 1,
                    "height": max(ys) - min(ys) + 1,
                }
            ]

            self._previous_screenshot = current.tobytes()
            return changed_regions

        except ImportError:
            logger.warning(
                "PIL not installed -- falling back to full screenshot comparison"
            )
            return self._fallback_diff(current_path)
        except Exception as e:
            logger.warning(f"Differential screenshot failed: {e}")
            return None

    def _fallback_diff(self, current_path: str) -> list[dict[str, Any]] | None:
        """Simple fallback without PIL."""
        current_data = Path(current_path).read_bytes()

        if self._previous_screenshot is None:
            self._previous_screenshot = current_data
            return None

        if current_data == self._previous_screenshot:
            return []

        self._previous_screenshot = current_data
        # Can't identify regions without PIL -- return full image
        try:
            from PIL import Image

            img = Image.open(current_path)
            return [{"x": 0, "y": 0, "width": img.width, "height": img.height}]
        except ImportError:
            return None

    def reset(self) -> None:
        """Clear the previous screenshot cache."""
        self._previous_screenshot = None
        self._previous_path = None

    def get_diff_screenshot(self, current_path: str, output_path: str) -> str:
        """Create a differential screenshot file with only changed regions.

        Args:
            current_path: Path to the current full screenshot.
            output_path: Path to write the differential screenshot.

        Returns:
            Path to the differential screenshot file, or current_path
            if no previous screenshot exists for comparison.
        """
        regions = self.get_changed_regions(current_path)

        if regions is None:
            # No previous screenshot -- return full
            return current_path

        if not regions:
            # No significant changes -- return a minimal indicator
            Path(output_path).write_bytes(b"")
            return output_path

        try:
            from PIL import Image

            current = Image.open(current_path)
            # Create new image with only changed regions highlighted
            diff_img = Image.new("RGB", current.size, (0, 0, 0))

            for region in regions:
                crop = current.crop(
                    (
                        region["x"],
                        region["y"],
                        region["x"] + region["width"],
                        region["y"] + region["height"],
                    )
                )
                diff_img.paste(crop, (region["x"], region["y"]))

            diff_img.save(output_path)
            return output_path

        except ImportError:
            logger.warning("PIL not installed -- returning full screenshot")
            return current_path
