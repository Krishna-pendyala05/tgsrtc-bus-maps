"""
Base Generator Class
====================
Abstract base class for all visualization generators.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import logging

from ..data.gtfs_loader import GTFSLoader
from ..config import OUTPUT_DIR

logger = logging.getLogger(__name__)


class BaseGenerator(ABC):
    """
    Abstract base class for visualization generators.
    
    All generators should inherit from this class and implement
    the generate() method.
    """
    
    # Default output filename (override in subclasses)
    output_filename = "output.html"
    
    def __init__(self, loader: Optional[GTFSLoader] = None):
        """
        Initialize the generator.
        
        Args:
            loader: GTFSLoader instance. If None, a new one is created.
        """
        self.loader = loader or GTFSLoader()
    
    @abstractmethod
    def generate(self) -> str:
        """
        Generate the HTML content.
        
        Must be implemented by subclasses.
        
        Returns:
            Complete HTML content as a string.
        """
        raise NotImplementedError("Subclasses must implement generate()")
    
    def save(self, output_path: Optional[Path] = None) -> Path:
        """
        Generate and save HTML to file.
        
        Args:
            output_path: Path to save the file. If None, uses default location.
            
        Returns:
            Path to the saved file.
        """
        if output_path is None:
            output_path = OUTPUT_DIR / self.output_filename
        else:
            output_path = Path(output_path)
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Generating {self.output_filename}...")
        html_content = self.generate()
        
        logger.info(f"Saving to {output_path}")
        output_path.write_text(html_content, encoding='utf-8')
        
        file_size = output_path.stat().st_size / 1024  # KB
        logger.info(f"Saved {output_path.name} ({file_size:.1f} KB)")
        
        return output_path
    
    def _log_progress(self, message: str) -> None:
        """Log a progress message."""
        print(f"  {message}")
        logger.info(message)
