# main.py
"""
People Connection Visualizer - Main Application Entry Point
A tool for visualizing and organizing relationships between individuals
"""

import tkinter as tk
import logging
from app import ConnectionApp

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point for the application"""
    logger.info("Starting People Connection Visualizer")
    
    # Create root window
    root = tk.Tk()
    
    # Create and run application
    app = ConnectionApp(root)
    
    logger.info("Starting main event loop")
    root.mainloop()
    
    logger.info("Application ended")

if __name__ == "__main__":
    main()