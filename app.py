# app.py
"""
Main application class for People Connection Visualizer
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging

from constants import COLORS, APP_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT
from models import Person
from canvas_manager import CanvasManager
from ui_manager import UIManager
from file_manager import FileManager
from dialogs import PersonDialog

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

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
    
    def export_to_png(self):
        """Export the current network diagram to PNG format at high DPI"""
        if not PIL_AVAILABLE:
            messagebox.showerror("Error", "PIL (Pillow) library is not installed.\n\nTo use PNG export, please install it with:\npip install Pillow")
            return
            
        if not self.people:
            messagebox.showwarning("Warning", "No people to export. Please add some people first.")
            return
            
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            title="Export Network as PNG (High DPI)"
        )
        
        if not filename:
            return
            
        try:
            # High DPI settings for crisp output
            dpi_scale = 3.0  # 3x scaling for high DPI (300 DPI equivalent)
            target_dpi = 300  # Target DPI for print quality
            
            # Calculate canvas bounds based on content
            if self.people:
                min_x = min(person.x for person in self.people.values()) - 300
                max_x = max(person.x for person in self.people.values()) + 300
                min_y = min(person.y for person in self.people.values()) - 200
                max_y = max(person.y for person in self.people.values()) + 200
            else:
                min_x, max_x, min_y, max_y = 0, 1200, 0, 800
            
            # Calculate canvas dimensions
            base_width = int(max_x - min_x)
            base_height = int(max_y - min_y)
            canvas_width = int(base_width * dpi_scale)
            canvas_height = int(base_height * dpi_scale)
            
            # Create a white background image at high resolution
            image = Image.new('RGB', (canvas_width, canvas_height), '#f8fafc')
            draw = ImageDraw.Draw(image)
            
            # Get current zoom level and apply DPI scaling
            base_zoom = self.canvas_manager.zoom_level if self.canvas_manager else 1.0
            zoom = base_zoom * dpi_scale
            
            # Offset for positioning
            offset_x = -min_x * zoom
            offset_y = -min_y * zoom
            
            # Draw grid pattern (scaled for high DPI)
            grid_size = int(40 * dpi_scale)
            grid_color = '#e2e8f0'
            grid_width = max(1, int(1 * dpi_scale))
            for x in range(0, canvas_width, grid_size):
                draw.line([(x, 0), (x, canvas_height)], fill=grid_color, width=grid_width)
            for y in range(0, canvas_height, grid_size):
                draw.line([(0, y), (canvas_width, y)], fill=grid_color, width=grid_width)
            
            # Draw connections first (so they appear behind people)
            if self.canvas_manager:
                for (id1, id2), elements in self.canvas_manager.connection_lines.items():
                    if id1 in self.people and id2 in self.people:
                        p1, p2 = self.people[id1], self.people[id2]
                        x1 = int(p1.x * zoom + offset_x)
                        y1 = int(p1.y * zoom + offset_y)
                        x2 = int(p2.x * zoom + offset_x)
                        y2 = int(p2.y * zoom + offset_y)
                        
                        # Get connection label
                        label = p1.connections.get(id2, "")
                        
                        # Draw connection line with DPI scaling
                        line_width = max(1, int(2 * dpi_scale))
                        draw.line([(x1, y1), (x2, y2)], fill=COLORS['primary'], width=line_width)
                        
                        # Draw connection label
                        if label and label.strip():
                            mid_x = (x1 + x2) // 2
                            mid_y = (y1 + y2) // 2
                            
                            # Try to load a font with DPI scaling
                            font_size = int(10 * dpi_scale)
                            try:
                                font = ImageFont.truetype("arial.ttf", font_size)
                            except:
                                try:
                                    font = ImageFont.load_default()
                                except:
                                    font = None
                            
                            # Get text size for background with DPI scaling
                            if font:
                                bbox = draw.textbbox((0, 0), label, font=font)
                                text_width = bbox[2] - bbox[0]
                                text_height = bbox[3] - bbox[1]
                            else:
                                text_width = int(len(label) * 6 * dpi_scale)
                                text_height = int(12 * dpi_scale)
                            
                            # Draw label background with DPI scaling
                            padding = int(4 * dpi_scale)
                            bg_left = mid_x - text_width // 2 - padding
                            bg_top = mid_y - text_height // 2 - padding
                            bg_right = mid_x + text_width // 2 + padding
                            bg_bottom = mid_y + text_height // 2 + padding
                            
                            border_width = max(1, int(1 * dpi_scale))
                            draw.rectangle([bg_left, bg_top, bg_right, bg_bottom], 
                                         fill='white', outline=COLORS['border'], width=border_width)
                            
                            # Draw label text
                            draw.text((mid_x - text_width // 2, mid_y - text_height // 2), 
                                    label, fill=COLORS['text_primary'], font=font)
            
            # Draw people cards
            for person_id, person in self.people.items():
                x = int(person.x * zoom + offset_x)
                y = int(person.y * zoom + offset_y)
                
                # Calculate card dimensions
                info_lines = [
                    f"Name: {person.name}" if person.name else "Name: Unnamed",
                    f"DOB: {person.dob}" if person.dob else "",
                    f"Alias: {person.alias}" if person.alias else "",
                    f"Addr: {person.address}" if person.address else "",
                    f"Phone: {person.phone}" if person.phone else ""
                ]
                info_lines = [line for line in info_lines if line.strip()]
                
                # Calculate card dimensions with DPI scaling
                card_width = max(max(len(line) for line in info_lines) * 9, 200) * zoom
                card_height = max(len(info_lines) * 25 + 40, 120) * zoom
                
                half_width = int(card_width // 2)
                half_height = int(card_height // 2)
                
                # Draw card shadow with DPI scaling
                shadow_offset = int(3 * dpi_scale)
                for i in range(3, 0, -1):
                    shadow_color = '#e0e0e0' if i == 3 else ('#d0d0d0' if i == 2 else '#c0c0c0')
                    offset = int(i * dpi_scale)
                    draw.rectangle([
                        x - half_width + offset, y - half_height + offset,
                        x + half_width + offset, y + half_height + offset
                    ], fill=shadow_color)
                
                # Draw main card with DPI scaling
                card_border_width = max(1, int(2 * dpi_scale))
                draw.rectangle([
                    x - half_width, y - half_height,
                    x + half_width, y + half_height
                ], fill=COLORS['surface'], outline=COLORS['primary'], width=card_border_width)
                
                # Draw header
                header_height = int(30 * zoom)
                draw.rectangle([
                    x - half_width, y - half_height,
                    x + half_width, y - half_height + header_height
                ], fill=COLORS['primary'])
                
                # Draw avatar background with DPI scaling
                avatar_size = int(20 * zoom)
                avatar_x = x - half_width + int(15 * zoom)
                avatar_y = y - half_height + int(15 * zoom)
                avatar_border_width = max(1, int(2 * dpi_scale))
                
                draw.ellipse([
                    avatar_x - avatar_size//2, avatar_y - avatar_size//2,
                    avatar_x + avatar_size//2, avatar_y + avatar_size//2
                ], fill='white', outline=COLORS['primary'], width=avatar_border_width)
                
                # Try to load fonts for text with DPI scaling
                name_font_size = int(11 * dpi_scale)
                detail_font_size = int(9 * dpi_scale)
                try:
                    name_font = ImageFont.truetype("arial.ttf", name_font_size)
                    detail_font = ImageFont.truetype("arial.ttf", detail_font_size)
                except:
                    try:
                        name_font = ImageFont.load_default()
                        detail_font = ImageFont.load_default()
                    except:
                        name_font = None
                        detail_font = None
                
                # Draw name in header
                name_x = avatar_x + avatar_size + int(10 * zoom)
                draw.text((name_x, avatar_y - int(6 * zoom)), 
                         person.name or "Unnamed", fill='white', font=name_font)
                
                # Draw details
                details_start_y = y - half_height + header_height + int(15 * zoom)
                line_height = int(20 * zoom)
                current_y = details_start_y
                
                details = [
                    ("DOB:", person.dob),
                    ("Alias:", person.alias),
                    ("Addr:", person.address),
                    ("Phone:", person.phone)
                ]
                
                for icon, value in details:
                    if value and value.strip():
                        label_x = x - half_width + int(15 * zoom)
                        # Fixed column width for labels to ensure proper alignment
                        label_column_width = int(60 * dpi_scale)  # Fixed width for label column
                        data_x = label_x + label_column_width
                        
                        # Draw label and data in separate columns
                        draw.text((label_x, current_y), icon, 
                                fill=COLORS['text_primary'], font=detail_font)
                        draw.text((data_x, current_y), value, 
                                fill=COLORS['text_primary'], font=detail_font)
                        current_y += line_height
            
            # Save the image with high DPI information
            image.save(filename, 'PNG', dpi=(target_dpi, target_dpi))
            messagebox.showinfo("Success", f"High DPI network exported successfully to:\n{filename}\n\nResolution: {canvas_width}x{canvas_height} pixels\nDPI: {target_dpi}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export PNG:\n{str(e)}")
            logger.error(f"Export error: {str(e)}")

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