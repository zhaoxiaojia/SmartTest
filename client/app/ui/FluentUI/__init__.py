__name__ = "FluentUI"
__version__ = "1.0.0"

# Export FluentUI module so `from FluentUI import FluentUI` works reliably
# (and so packagers can discover the submodule deterministically).
from . import FluentUI  # noqa: F401

__all__ = ["FluentUI"]
