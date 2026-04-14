"""Image comparison utilities using Pillow.

This module provides a simple helper class to compare two image files using
the Pillow library. When differences are found between two images, the
differences can be saved to a specified location.  All parameters are
documented using a ``Parameters`` section for clarity.
"""


import logging
from PIL import Image, ImageChops


class PilTool:
    """Utility class for comparing images using the Pillow library.

    Instances of this class expose methods for comparing two image files and
    optionally saving a visual diff image when differences are detected. The
    comparison is performed using :func:`ImageChops.difference` and the
    presence of a bounding box is used to determine whether the images differ.
    """

    def __init__(self) -> None:
        """Initialize a new :class:`PilTool` instance.

        This constructor currently performs no work but exists for parity
        with other tools that may require initialization.
        """
        # No initialization required for this simple helper.
        ...

    def compare_images(self, path_one: str, path_two: str, diff_save_location: str) -> None:
        """Compare two images and optionally save a diff image.

        Two images are opened from the provided file paths and compared pixel by
        pixel using Pillow's :func:`ImageChops.difference`.  If the resulting
        difference image contains no non-zero pixels then the images are
        considered identical and a message is logged.  Otherwise the diff
        image is saved to the provided location.

        Parameters:
            path_one (str): Path to the first image file.
            path_two (str): Path to the second image file.
            diff_save_location (str): File path where any generated diff
                image should be saved.

        Returns:
            None
        """
        image_one = Image.open(path_one)
        image_two = Image.open(path_two)
        try:
            diff = ImageChops.difference(image_one, image_two)
            # If diff.getbbox() returns None there are no differences.
            if diff.getbbox() is None:
                logging.info("Images are identical; no diff generated.")
            else:
                diff.save(diff_save_location)
        except ValueError as e:
            # ValueError occurs when image sizes or boxes do not match.
            text = (
                "Images differ in size or coordinate box; ensure both images "
                "have the same dimensions and that the coordinates provided "
                "are compatible."
            )
            logging.error("%s %s", e, text)
