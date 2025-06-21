# app.py
"""
Main application class for People Connection Visualizer
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from constants import COLORS, APP_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT
from models import Person
from canvas_manager import CanvasManager
from ui_manager import UIManager
from file_manager import FileManager
from dialogs import PersonDialog

logger = logging.getLogger(__name__)

class ConnectionApp:
    """Main application class that coordinates all components"""
    
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.configure(bg=COLORS['background'])
        
        # Data structures
        self.people = {}  # {id: Person}
        self.next_id = 1
        
        # Initialize managers
        self.canvas_manager = None
        self.ui_manager = UIManager(self)
        self.file_manager = FileManager(self)
        
        # Setup UI
        self.setup_ui()
        
        logger.info("Application initialized successfully")
    
    def setup_ui(self):
        """Initialize the user interface"""
        # Create main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Let UI manager create the interface
        canvas = self.ui_manager.create_ui(main_container)
        
        # Force update to ensure canvas has proper dimensions
        self.root.update_idletasks()
        
        # Initialize canvas manager with the created canvas
        self.canvas_manager = CanvasManager(canvas, self)
        
    def add_person(self):
        """Add a new person to the visualization"""
        logger.info("Adding new person")
        
        dialog = PersonDialog(self.root, "Add Person")
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            person = Person(**dialog.result)
            person_id = self.next_id
            self.next_id += 1
            
            # Calculate position using grid layout
            person.x, person.y = self.canvas_manager.calculate_person_position(len(self.people))
            
            logger.info(f"Person positioned at world coords: ({person.x}, {person.y})")
            
            # Add to data structure
            self.people[person_id] = person
            
            # Create visual representation
            self.canvas_manager.create_person_widget(person_id)
            
            self.ui_manager.update_status(f"Added {person.name}")
            logger.info(f"Added person: {person.name} with ID {person_id}")
    
    def edit_person(self, person_id):
        """Edit an existing person's information"""
        if person_id not in self.people:
            return
            
        person = self.people[person_id]
        dialog = PersonDialog(
            self.root, 
            "Edit Person",
            name=person.name,
            dob=person.dob,
            alias=person.alias,
            address=person.address,
            phone=person.phone
        )
        
        self.root.wait_window(dialog.dialog)
        
        if dialog.result:
            # Update person data
            for key, value in dialog.result.items():
                setattr(person, key, value)
            
            # Update visual representation
            self.canvas_manager.refresh_person_widget(person_id)
            
            self.ui_manager.update_status(f"Updated {person.name}")
            logger.info(f"Updated person: {person.name}")
    
    def delete_person(self, person_id):
        """Delete a person and all their connections"""
        if person_id not in self.people:
            return
            
        person = self.people[person_id]
        
        # Confirm deletion
        result = messagebox.askyesno(
            "Delete Person",
            f"Are you sure you want to delete {person.name} and all their connections?",
            parent=self.root
        )
        
        if result:
            # Remove all connections to this person
            for other_id in list(person.connections.keys()):
                self.canvas_manager.remove_connection(person_id, other_id)
            
            # Remove connections from other people to this person
            for other_id, other_person in self.people.items():
                if person_id in other_person.connections:
                    del other_person.connections[person_id]
            
            # Remove visual representation
            self.canvas_manager.delete_person_widget(person_id)
            
            # Remove from data structure
            del self.people[person_id]
            
            self.ui_manager.update_status(f"Deleted {person.name}")
            logger.info(f"Deleted person: {person.name}")
    
    def clear_all(self):
        """Clear all data and reset the application"""
        result = messagebox.askyesno(
            "Clear All",
            "Are you sure you want to clear all data? This cannot be undone.",
            parent=self.root
        )
        
        if result:
            self.canvas_manager.clear_all()
            self.people.clear()
            self.next_id = 1
            self.ui_manager.update_status("All data cleared")
            logger.info("Cleared all data")
    
    def save_data(self):
        """Save data to file"""
        self.file_manager.save_data()
    
    def load_data(self):
        """Load data from file"""
        self.file_manager.load_data()