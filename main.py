import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import csv
import math
from datetime import datetime
import os
from collections import defaultdict
import logging
import zipfile
import shutil
import tempfile
import json
import urllib.request
import urllib.error
import threading
from functools import lru_cache

# Try to import PIL for PNG export functionality
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Import from supporting modules
from src.constants import COLORS, CARD_COLORS
from src.models import Person, TextboxCard, LegendCard
from src.dialogs import PersonDialog, TextboxDialog, LegendDialog, ConnectionLabelDialog, VersionUpdateDialog, NoUpdateDialog
from src.utils import setup_logging, darken_color
from src.ui_setup import UISetup
from src.event_handlers import EventHandlers
from src.data_management import DataManagement
from src.canvas_helpers import CanvasHelpers

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)



class ConnectionApp:
    def __init__(self, root):
        logger.info("Initializing ConnectionApp")
        self.root = root
        self.root.title("COMRADE")
        self.root.geometry("1500x900")
        self.root.configure(bg=COLORS['background'])
        
        # Data structures
        self.people = {}  # {id: Person}
        self.textboxes = {}  # {id: TextboxCard}
        self.legends = {}  # {id: LegendCard}
        self.person_widgets = {}  # {id: canvas_item_id}
        self.textbox_widgets = {}  # {id: canvas_item_id}
        self.legend_widgets = {}  # {id: canvas_item_id}
        self.connection_lines = {}  # {(id1, id2): (line_id, label_id)}
        self.original_font_sizes = {}  # {canvas_item_id: original_font_size} for proper text scaling
        self.original_image_sizes = {}  # {canvas_item_id: (original_width, original_height)} for proper image scaling
        self.image_cache = {}  # {(file_path, width, height): PhotoImage} for caching resized images
        
        # Optimized image caching for zoom performance
        self.scaled_image_cache = {}  # {(image_path, scale_factor): PhotoImage}
        self.base_image_cache = {}   # {image_path: PIL.Image} - original PIL images
        self.current_scale = 1.0     # Track current zoom level
        self.max_cache_size = 50     # Limit cache size to prevent memory issues
        self.zoom_debounce_timer = None  # Timer for debouncing zoom events
        
        self.selected_person = None
        self.selected_textbox = None
        self.selected_legend = None
        self.selected_connection = None  # Track selected connection for editing/deletion
        self.dragging = False
        self.drag_data = {"x": 0, "y": 0}
        self.connecting = False
        self.connection_start = None
        self.temp_line = None
        self.next_id = 1
        
        # Initialize helpers first, as UI setup depends on them
        self.events = EventHandlers(self)
        self.data = DataManagement(self)
        self.canvas_helpers = CanvasHelpers(self)

        logger.info("Setting up UI")
        self.ui = UISetup(self)
        self.ui.setup_styles()
        self.ui.setup_ui()
        
        # Clean up old extracted files on startup
        self.data.cleanup_old_files()
        
        # Check for updates automatically on startup (with a delay to let UI load)
        self.root.after(2000, self.data.check_for_updates_silently)  # 2 second delay
        
        logger.info("ConnectionApp initialized successfully")
    
    def refresh_person_widget(self, person_id):
        """Refresh a person's widget on the canvas"""
        # Don't refresh during zoom operations to avoid double-scaling
        if hasattr(self.events, '_zooming') and self.events._zooming:
            return
            
        logger.info(f"Refreshing widget for person {person_id}")
        
        # Remove the old widget from the canvas
        if person_id in self.person_widgets:
            for item in self.person_widgets[person_id]:
                self.canvas.delete(item)
            del self.person_widgets[person_id]
        
        # Re-create the widget with the current zoom level
        zoom = self.events.last_zoom
        self.canvas_helpers.create_person_widget(person_id, zoom)
        
        # Redraw connections to ensure they are correctly positioned
        self.canvas_helpers.update_connections()
        logger.info(f"Widget for person {person_id} refreshed")

    def refresh_textbox_widget(self, textbox_id):
        """Refresh a textbox's widget on the canvas"""
        # Don't refresh during zoom operations to avoid double-scaling
        if hasattr(self.events, '_zooming') and self.events._zooming:
            return
            
        logger.info(f"Refreshing widget for textbox {textbox_id}")
        
        # Remove the old widget from the canvas
        if textbox_id in self.textbox_widgets:
            for item in self.textbox_widgets[textbox_id]:
                self.canvas.delete(item)
            del self.textbox_widgets[textbox_id]
        
        # Re-create the widget with the current zoom level
        zoom = self.events.last_zoom
        self.canvas_helpers.create_textbox_widget(textbox_id, zoom)
        
        # Redraw connections to ensure they are correctly positioned
        self.canvas_helpers.update_connections()
        logger.info(f"Widget for textbox {textbox_id} refreshed")

    def add_person(self):
        logger.info("Add person button clicked")
        dialog = PersonDialog(self.root, "Add Person")
        self.root.wait_window(dialog.dialog)  # Wait for dialog to close
        logger.info(f"Dialog result: {dialog.result}")
        if dialog.result:
            # Extract files separately since Person.__init__ doesn't accept it
            files = dialog.result.pop('files', [])
            person = Person(**dialog.result)
            person.files = files  # Set files after creation
            person_id = self.next_id
            self.next_id += 1
            logger.info(f"Creating person with ID {person_id}: {person.name}")
            
            # Always place new person card at (500, 500)
            person.x = 500
            person.y = 500
            logger.info(f"Positioned person at (500, 500)")
            
            self.people[person_id] = person
            logger.info(f"Added person to data structure. Total people: {len(self.people)}")
            self.canvas_helpers.create_person_widget(person_id)
            logger.info(f"Created widget for person {person_id}")
        else:
            logger.info("Dialog was cancelled")
            
    def add_textbox(self):
        logger.info("Add textbox button clicked")
        dialog = TextboxDialog(self.root, "Add Textbox Card")
        self.root.wait_window(dialog.dialog)  # Wait for dialog to close
        logger.info(f"Dialog result: {dialog.result}")
        if dialog.result:
            textbox = TextboxCard(**dialog.result)
            textbox_id = self.next_id
            self.next_id += 1
            logger.info(f"Creating textbox with ID {textbox_id}: {textbox.title}")
            
            # Always place new textbox card at (500, 500)
            textbox.x = 500
            textbox.y = 500
            logger.info(f"Positioned textbox at (500, 500)")
            
            self.textboxes[textbox_id] = textbox
            logger.info(f"Added textbox to data structure. Total textboxes: {len(self.textboxes)}")
            self.canvas_helpers.create_textbox_widget(textbox_id)
            logger.info(f"Created widget for textbox {textbox_id}")
        else:
            logger.info("Dialog was cancelled")

    def edit_legend(self):
        logger.info("Edit legend button clicked")
        
        # Find existing legend or create one if none exists
        legend_id = None
        legend = None
        
        if self.legends:
            # Use the first (and should be only) legend
            legend_id = list(self.legends.keys())[0]
            legend = self.legends[legend_id]
            logger.info(f"Found existing legend with ID {legend_id}: {legend.title}")
        else:
            # Create a new legend since none exists
            legend = LegendCard(title="Legend", color_entries={})
            legend_id = self.next_id
            self.next_id += 1
            logger.info(f"Creating new legend with ID {legend_id}")
            
            # Position using box layout (offset from people and textboxes)
            cols = 2
            col_width = 400
            row_height = 200
            start_x = 200
            start_y = 120
            total_cards = len(self.people) + len(self.textboxes) + len(self.legends)
            row = total_cards // cols
            col = total_cards % cols
            legend.x = start_x + col * col_width
            legend.y = start_y + row * row_height
            logger.info(f"Positioned legend at ({legend.x}, {legend.y})")
            
            self.legends[legend_id] = legend
            self.canvas_helpers.create_legend_widget(legend_id)
        
        # Open dialog to edit the legend
        dialog = LegendDialog(self.root, "Edit Legend Card", 
                             legend_title=legend.title, 
                             color_entries=legend.color_entries)
        self.root.wait_window(dialog.dialog)  # Wait for dialog to close
        logger.info(f"Dialog result: {dialog.result}")
        
        if dialog.result:
            # Update the existing legend
            legend.title = dialog.result['title']
            legend.color_entries = dialog.result['color_entries']
            
            # Refresh the legend widget
            self.refresh_legend_widget(legend_id)
            logger.info(f"Updated legend '{legend.title}'")
        else:
            logger.info("Dialog was cancelled")

    def refresh_legend_widget(self, legend_id):
        """Refresh a legend's widget on the canvas"""
        # Don't refresh during zoom operations to avoid double-scaling
        if hasattr(self.events, '_zooming') and self.events._zooming:
            return
            
        logger.info(f"Refreshing widget for legend {legend_id}")
        # Remove the existing widget
        if legend_id in self.legend_widgets:
            legend_items = self.legend_widgets[legend_id]
            for item in legend_items:
                self.canvas.delete(item)
            del self.legend_widgets[legend_id]
        
        # Create a new widget with current zoom level
        self.canvas_helpers.create_legend_widget(legend_id, zoom=self.events.last_zoom)
        logger.info(f"Refreshed widget for legend {legend_id}")

    def delete_person(self):
        """Delete the currently selected person"""
        if self.events.selected_person is None:
            messagebox.showwarning("No Selection", "Please select a person to delete by clicking on them first.")
            return
            
        person_id = self.events.selected_person
        person = self.people[person_id]
        
        # Confirm deletion
        result = messagebox.askyesno(
            "Confirm Deletion", 
            f"Are you sure you want to delete '{person.name}'?\n\nThis will also remove all their connections.",
            icon='warning'
        )
        
        if not result:
            return
            
        logger.info(f"Deleting person {person_id}: {person.name}")
        
        # Remove all connections involving this person
        connections_to_remove = []
        for other_id in list(person.connections.keys()):
            if other_id in self.people:
                # Remove the connection from the other person's connections
                if person_id in self.people[other_id].connections:
                    del self.people[other_id].connections[person_id]
                
                # Track connection lines to remove
                connection_key = (min(person_id, other_id), max(person_id, other_id))
                connections_to_remove.append(connection_key)
        
        # Remove connection lines from canvas
        for connection_key in connections_to_remove:
            if connection_key in self.connection_lines:
                elements = self.connection_lines[connection_key]
                for element in elements:
                    self.canvas.delete(element)
                    # Clean up font size tracking for text items
                    if element in self.original_font_sizes:
                        del self.original_font_sizes[element]
                del self.connection_lines[connection_key]
        
        # Remove person widget from canvas
        if person_id in self.person_widgets:
            widget_items = self.person_widgets[person_id]
            for item in widget_items:
                self.canvas.delete(item)
                # Clean up tracking dictionaries
                if item in self.original_font_sizes:
                    del self.original_font_sizes[item]
                if item in self.original_image_sizes:
                    del self.original_image_sizes[item]
            del self.person_widgets[person_id]
        
        # Remove from people dictionary
        del self.people[person_id]
        
        # Clear selection
        self.events.selected_person = None
        
        logger.info(f"Successfully deleted person {person_id}")
        self.update_status(f"🗑️ Deleted '{person.name}' and their connections")
        
        # Update canvas
        self.canvas.update()

    def delete_textbox(self):
        """Delete the currently selected textbox"""
        if self.events.selected_textbox is None:
            messagebox.showwarning("No Selection", "Please select a textbox to delete by clicking on it first.")
            return
            
        textbox_id = self.events.selected_textbox
        textbox = self.textboxes[textbox_id]
        
        # Confirm deletion
        result = messagebox.askyesno(
            "Confirm Deletion", 
            f"Are you sure you want to delete textbox '{textbox.title}'?\n\nThis will also remove all its connections.",
            icon='warning'
        )
        
        if not result:
            return
            
        logger.info(f"Deleting textbox {textbox_id}: {textbox.title}")
        
        # Remove all connections involving this textbox
        connections_to_remove = []
        for other_id in list(textbox.connections.keys()):
            # Check if connected to person, textbox, or legend
            other_card = self.people.get(other_id) or self.textboxes.get(other_id) or self.legends.get(other_id)
            if other_card:
                # Remove the connection from the other card's connections
                if textbox_id in other_card.connections:
                    del other_card.connections[textbox_id]
                
                # Track connection lines to remove
                connection_key = (min(textbox_id, other_id), max(textbox_id, other_id))
                connections_to_remove.append(connection_key)
        
        # Remove connection lines from canvas
        for connection_key in connections_to_remove:
            if connection_key in self.connection_lines:
                elements = self.connection_lines[connection_key]
                for element in elements:
                    self.canvas.delete(element)
                    # Clean up font size tracking for text items
                    if element in self.original_font_sizes:
                        del self.original_font_sizes[element]
                del self.connection_lines[connection_key]
        
        # Remove textbox widget from canvas
        if textbox_id in self.textbox_widgets:
            widget_items = self.textbox_widgets[textbox_id]
            for item in widget_items:
                self.canvas.delete(item)
                # Clean up tracking dictionaries
                if item in self.original_font_sizes:
                    del self.original_font_sizes[item]
                if item in self.original_image_sizes:
                    del self.original_image_sizes[item]
            del self.textbox_widgets[textbox_id]
        
        # Remove from textboxes dictionary
        del self.textboxes[textbox_id]
        
        # Clear selection
        self.events.selected_textbox = None
        
        logger.info(f"Successfully deleted textbox {textbox_id}")
        self.update_status(f"🗑️ Deleted textbox '{textbox.title}' and its connections")
        
        # Update canvas
        self.canvas.update()

    def delete_legend(self):
        """Delete the currently selected legend"""
        if self.events.selected_legend is None:
            messagebox.showwarning("No Selection", "Please select a legend to delete by clicking on it first.")
            return
            
        legend_id = self.events.selected_legend
        legend = self.legends[legend_id]
        
        # Confirm deletion
        result = messagebox.askyesno(
            "Confirm Deletion", 
            f"Are you sure you want to delete legend '{legend.title}'?\n\nThis will also remove all its connections.",
            icon='warning'
        )
        
        if not result:
            return
            
        logger.info(f"Deleting legend {legend_id}: {legend.title}")
        
        # Remove all connections involving this legend
        connections_to_remove = []
        for other_id in list(legend.connections.keys()):
            # Check if connected to person, textbox, or legend
            other_card = self.people.get(other_id) or self.textboxes.get(other_id) or self.legends.get(other_id)
            if other_card:
                # Remove the connection from the other card's connections
                if legend_id in other_card.connections:
                    del other_card.connections[legend_id]
                
                # Track connection lines to remove
                connection_key = (min(legend_id, other_id), max(legend_id, other_id))
                connections_to_remove.append(connection_key)
        
        # Remove connection lines from canvas
        for connection_key in connections_to_remove:
            if connection_key in self.connection_lines:
                elements = self.connection_lines[connection_key]
                for element in elements:
                    self.canvas.delete(element)
                    # Clean up font size tracking for text items
                    if element in self.original_font_sizes:
                        del self.original_font_sizes[element]
                del self.connection_lines[connection_key]
        
        # Remove legend widget from canvas
        if legend_id in self.legend_widgets:
            widget_items = self.legend_widgets[legend_id]
            for item in widget_items:
                self.canvas.delete(item)
                # Clean up tracking dictionaries
                if item in self.original_font_sizes:
                    del self.original_font_sizes[item]
                if item in self.original_image_sizes:
                    del self.original_image_sizes[item]
            del self.legend_widgets[legend_id]
        
        # Remove from legends dictionary
        del self.legends[legend_id]
        
        # Clear selection
        self.events.selected_legend = None
        
        logger.info(f"Successfully deleted legend {legend_id}")
        self.update_status(f"🗑️ Deleted legend '{legend.title}' and its connections")
        
        # Update canvas
        self.canvas.update()

    def delete_selected(self):
        """Delete the currently selected card (person, textbox, or legend)"""
        if self.events.selected_person:
            self.delete_person()
        elif self.events.selected_textbox:
            self.delete_textbox()
        elif self.events.selected_legend:
            self.delete_legend()
        else:
            messagebox.showwarning("No Selection", "Please select a card (person, textbox, or legend) to delete by clicking on it first.")
            
    def clear_all(self):
        """Clear all people, connections, and reset the canvas"""
        self.data.clear_all()

    def update_status(self, message, duration=5000):
        """Update the status bar with a message that disappears after a duration"""
        self.status_label.config(text=message)
        # If a timer is already running, cancel it
        if hasattr(self, "status_timer") and self.status_timer:
            self.root.after_cancel(self.status_timer)
        # Set a new timer to clear the message
        self.status_timer = self.root.after(duration, self.clear_status)

    def clear_status(self):
        """Clear the status bar message"""
        self.status_label.config(text="Ready - Right-click a person to start linking")
        self.status_timer = None

    def draw_connection(self, id1, id2, label, zoom):
        """Delegate to canvas_helpers"""
        self.canvas_helpers.draw_connection(id1, id2, label, zoom)

    # All data management methods are now in DataManagement class
    def save_data(self):
        self.data.save_data()

    def load_data(self):
        self.data.load_data()

    def export_to_png(self):
        self.data.export_to_png()

    def check_for_updates(self, silent=False):
        self.data.check_for_updates(silent)

    def check_for_updates_silently(self):
        self.data.check_for_updates_silently()

    def cleanup_old_files(self):
        self.data.cleanup_old_files()

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = ConnectionApp(root)
        root.mainloop()
    except Exception as e:
        logger.critical(f"Unhandled exception in main loop: {e}", exc_info=True)
        messagebox.showerror("Fatal Error", f"A critical error occurred: {e}")