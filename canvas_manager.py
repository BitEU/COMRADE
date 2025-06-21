# canvas_manager.py
"""
Canvas Manager - Handles all canvas operations, drawing, and transformations
"""

import tkinter as tk
import math
import logging
from constants import COLORS, GRID_SIZE, BOX_LAYOUT_COLS, BOX_LAYOUT_COL_WIDTH, BOX_LAYOUT_ROW_HEIGHT, BOX_LAYOUT_START_X, BOX_LAYOUT_START_Y
from dialogs import ConnectionLabelDialog

logger = logging.getLogger(__name__)

class CanvasManager:
    """Manages all canvas operations including drawing, zooming, and panning"""
    
    def __init__(self, canvas, app):
        self.canvas = canvas
        self.app = app
        
        # Visual elements tracking
        self.person_widgets = {}  # {id: [canvas_item_ids]}
        self.connection_lines = {}  # {(id1, id2): [canvas_item_ids]}
        
        # Interaction state
        self.selected_person = None
        self.selected_connection = None
        self.dragging = False
        self.drag_start = {"x": 0, "y": 0}
        self.connecting = False
        self.connection_start = None
        self.temp_line = None
        
        # Transform state - Initialize with no offset
        self.zoom_level = 1.0
        self.pan_offset = {"x": 0, "y": 0}
        
        # Setup canvas
        self.setup_canvas()
        
    def setup_canvas(self):
        """Initialize canvas with event bindings"""
        # Mouse events
        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        
        # Middle mouse for panning
        self.canvas.bind("<Button-2>", self.on_middle_press)
        self.canvas.bind("<B2-Motion>", self.on_middle_drag)
        self.canvas.bind("<ButtonRelease-2>", self.on_middle_release)
        
        # Mouse wheel for zooming
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Control-MouseWheel>", self.on_mouse_wheel)
        
        # Keyboard events
        self.canvas.bind("<Escape>", self.on_escape)
        self.canvas.bind("<Delete>", self.on_delete)
        
        # Make canvas focusable
        self.canvas.configure(takefocus=True)
        
        # Configure canvas resize
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        
        # Wait for canvas to be fully realized
        self.canvas.update_idletasks()
        
        # Draw initial grid
        self.draw_grid()
    
    def on_canvas_resize(self, event):
        """Handle canvas resize event"""
        # Redraw grid when canvas is resized
        self.draw_grid()
    
    def world_to_screen(self, x, y):
        """Convert world coordinates to screen coordinates"""
        screen_x = (x * self.zoom_level) + self.pan_offset["x"]
        screen_y = (y * self.zoom_level) + self.pan_offset["y"]
        return screen_x, screen_y
    
    def screen_to_world(self, x, y):
        """Convert screen coordinates to world coordinates"""
        world_x = (x - self.pan_offset["x"]) / self.zoom_level
        world_y = (y - self.pan_offset["y"]) / self.zoom_level
        return world_x, world_y
    
    def draw_grid(self):
        """Draw background grid"""
        self.canvas.delete("grid")
        
        # Get canvas dimensions
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        
        if width <= 1 or height <= 1:
            # Canvas not ready yet, try again later
            self.canvas.after(100, self.draw_grid)
            return
        
        # Calculate grid spacing based on zoom
        grid_spacing = GRID_SIZE * self.zoom_level
        
        # Calculate grid offset based on pan
        offset_x = self.pan_offset["x"] % grid_spacing
        offset_y = self.pan_offset["y"] % grid_spacing
        
        # Draw vertical lines
        x = offset_x
        while x < width:
            self.canvas.create_line(
                x, 0, x, height,
                fill=COLORS['border'],
                width=1,
                tags="grid"
            )
            x += grid_spacing
        
        # Draw horizontal lines
        y = offset_y
        while y < height:
            self.canvas.create_line(
                0, y, width, y,
                fill=COLORS['border'],
                width=1,
                tags="grid"
            )
            y += grid_spacing
        
        # Send grid to back
        self.canvas.tag_lower("grid")
    
    def calculate_person_position(self, index):
        """Calculate position for a new person using grid layout"""
        row = index // BOX_LAYOUT_COLS
        col = index % BOX_LAYOUT_COLS
        x = BOX_LAYOUT_START_X + col * BOX_LAYOUT_COL_WIDTH
        y = BOX_LAYOUT_START_Y + row * BOX_LAYOUT_ROW_HEIGHT
        return x, y
    
    def center_view_on_content(self):
        """Center the view on all content"""
        bbox = self.canvas.bbox("person")
        if bbox:
            x1, y1, x2, y2 = bbox
            content_center_x = (x1 + x2) / 2
            content_center_y = (y1 + y2) / 2
            
            canvas_center_x = self.canvas.winfo_width() / 2
            canvas_center_y = self.canvas.winfo_height() / 2
            
            # Calculate pan offset to center content
            self.pan_offset["x"] = canvas_center_x - content_center_x
            self.pan_offset["y"] = canvas_center_y - content_center_y
            
            # Update display
            self.update_all_positions()
            
            logger.info(f"Centered view: pan offset = ({self.pan_offset['x']}, {self.pan_offset['y']})")
    
    def create_person_widget(self, person_id):
        """Create visual representation of a person"""
        if person_id not in self.app.people:
            logger.error(f"Person {person_id} not found in app.people")
            return
            
        person = self.app.people[person_id]
        
        # Log creation
        logger.info(f"Creating widget for person {person_id}: {person.name}")
        logger.info(f"World position: ({person.x}, {person.y})")
        
        # Convert world position to screen position
        x, y = self.world_to_screen(person.x, person.y)
        logger.info(f"Screen position: ({x}, {y})")
        
        # Calculate dimensions
        info_lines = self._get_person_info_lines(person)
        width = max(200, max(len(line) * 8 for line in info_lines) if info_lines else 200)
        height = max(120, len(info_lines) * 25 + 40)
        
        # Create widget group
        group = []
        
        # Shadow
        shadow = self.canvas.create_rectangle(
            x - width//2 + 3, y - height//2 + 3,
            x + width//2 + 3, y + height//2 + 3,
            fill='#e0e0e0',
            outline='',
            tags=(f"person_{person_id}", "person", "shadow")
        )
        group.append(shadow)
        
        # Main card
        card = self.canvas.create_rectangle(
            x - width//2, y - height//2,
            x + width//2, y + height//2,
            fill=COLORS['surface'],
            outline=COLORS['primary'],
            width=2,
            tags=(f"person_{person_id}", "person", "card")
        )
        group.append(card)
        
        # Header
        header = self.canvas.create_rectangle(
            x - width//2, y - height//2,
            x + width//2, y - height//2 + 30,
            fill=COLORS['primary'],
            outline='',
            tags=(f"person_{person_id}", "person", "header")
        )
        group.append(header)
        
        # Name text
        name_text = self.canvas.create_text(
            x, y - height//2 + 15,
            text=person.name or "Unnamed",
            font=("Segoe UI", 11, "bold"),
            fill='white',
            tags=(f"person_{person_id}", "person", "name")
        )
        group.append(name_text)
        
        # Info text
        info_y = y - height//2 + 45
        for line in info_lines[1:]:  # Skip name
            if line.strip():
                text = self.canvas.create_text(
                    x - width//2 + 10, info_y,
                    text=line,
                    anchor="w",
                    font=("Segoe UI", 9),
                    fill=COLORS['text_primary'],
                    tags=(f"person_{person_id}", "person", "info")
                )
                group.append(text)
                info_y += 20
        
        # Store widget group
        self.person_widgets[person_id] = group
        
        # Ensure person widgets are above grid
        for item in group:
            self.canvas.tag_raise(item)
        
        # Log for debugging
        logger.info(f"Created {len(group)} canvas items for person {person_id}")
        logger.info(f"Canvas bbox for this person: {self.canvas.bbox(f'person_{person_id}')}")
        logger.info(f"Total canvas bbox: {self.canvas.bbox('all')}")
        
        # Update connections if any exist
        self.update_person_connections(person_id)
    
    def _get_person_info_lines(self, person):
        """Get formatted info lines for a person"""
        lines = [person.name or "Unnamed"]
        if person.dob:
            lines.append(f"🎂 {person.dob}")
        if person.alias:
            lines.append(f"🏷️ {person.alias}")
        if person.address:
            lines.append(f"🏠 {person.address}")
        if person.phone:
            lines.append(f"📞 {person.phone}")
        return lines
    
    def refresh_person_widget(self, person_id):
        """Refresh the visual representation of a person"""
        # Delete old widget if it exists
        if person_id in self.person_widgets:
            self.delete_person_widget(person_id)
        
        # Create new widget
        self.create_person_widget(person_id)
    
    def delete_person_widget(self, person_id):
        """Remove visual representation of a person"""
        if person_id in self.person_widgets:
            for item in self.person_widgets[person_id]:
                self.canvas.delete(item)
            del self.person_widgets[person_id]
    
    def update_person_connections(self, person_id):
        """Update all connections for a person"""
        person = self.app.people.get(person_id)
        if not person:
            return
            
        for other_id in person.connections:
            if other_id in self.app.people:
                self.update_connection_line(person_id, other_id)
    
    def create_connection(self, from_id, to_id):
        """Create a connection between two people"""
        # Check if connection already exists
        if to_id in self.app.people[from_id].connections:
            logger.warning(f"Connection already exists between {from_id} and {to_id}")
            return
        
        # Get connection label
        dialog = ConnectionLabelDialog(self.app.root, "Add Connection")
        self.app.root.wait_window(dialog.dialog)
        
        if dialog.result:
            # Add to data model
            self.app.people[from_id].connections[to_id] = dialog.result
            self.app.people[to_id].connections[from_id] = dialog.result
            
            # Draw connection
            self.draw_connection(from_id, to_id, dialog.result)
            
            # Update status
            from_name = self.app.people[from_id].name
            to_name = self.app.people[to_id].name
            self.app.ui_manager.update_status(f"Connected {from_name} to {to_name}")
    
    def draw_connection(self, id1, id2, label):
        """Draw a connection line between two people"""
        # Ensure consistent ordering
        key = (min(id1, id2), max(id1, id2))
        
        # Remove existing connection if any
        if key in self.connection_lines:
            for item in self.connection_lines[key]:
                self.canvas.delete(item)
        
        # Get person positions
        p1 = self.app.people[id1]
        p2 = self.app.people[id2]
        
        # Convert to screen coordinates
        x1, y1 = self.world_to_screen(p1.x, p1.y)
        x2, y2 = self.world_to_screen(p2.x, p2.y)
        
        # Create connection elements
        elements = []
        
        # Connection line
        line = self.canvas.create_line(
            x1, y1, x2, y2,
            fill=COLORS['secondary'],
            width=3,
            smooth=True,
            tags=("connection", f"connection_{key[0]}_{key[1]}")
        )
        elements.append(line)
        
        # Label background
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        
        label_bg = self.canvas.create_rectangle(
            mid_x - 50, mid_y - 15,
            mid_x + 50, mid_y + 15,
            fill=COLORS['surface'],
            outline=COLORS['secondary'],
            width=2,
            tags=("connection", f"connection_{key[0]}_{key[1]}")
        )
        elements.append(label_bg)
        
        # Label text
        label_text = self.canvas.create_text(
            mid_x, mid_y,
            text=label,
            font=("Segoe UI", 10),
            fill=COLORS['text_primary'],
            tags=("connection", f"connection_{key[0]}_{key[1]}")
        )
        elements.append(label_text)
        
        # Store connection elements
        self.connection_lines[key] = elements
        
        # Layer properly
        self.canvas.tag_lower(line)
        self.canvas.tag_raise(label_bg)
        self.canvas.tag_raise(label_text)
    
    def update_connection_line(self, id1, id2):
        """Update the position of a connection line"""
        key = (min(id1, id2), max(id1, id2))
        
        if key in self.connection_lines:
            # Get connection elements
            elements = self.connection_lines[key]
            if len(elements) >= 3:
                line, label_bg, label_text = elements[:3]
                
                # Get positions
                p1 = self.app.people[id1]
                p2 = self.app.people[id2]
                
                # Convert to screen coordinates
                x1, y1 = self.world_to_screen(p1.x, p1.y)
                x2, y2 = self.world_to_screen(p2.x, p2.y)
                
                # Update line
                self.canvas.coords(line, x1, y1, x2, y2)
                
                # Update label position
                mid_x = (x1 + x2) / 2
                mid_y = (y1 + y2) / 2
                
                self.canvas.coords(label_bg, 
                    mid_x - 50, mid_y - 15,
                    mid_x + 50, mid_y + 15
                )
                self.canvas.coords(label_text, mid_x, mid_y)
    
    def remove_connection(self, id1, id2):
        """Remove a connection between two people"""
        key = (min(id1, id2), max(id1, id2))
        
        if key in self.connection_lines:
            # Remove visual elements
            for item in self.connection_lines[key]:
                self.canvas.delete(item)
            del self.connection_lines[key]
        
        # Remove from data model
        if id2 in self.app.people[id1].connections:
            del self.app.people[id1].connections[id2]
        if id1 in self.app.people[id2].connections:
            del self.app.people[id2].connections[id1]
    
    def update_all_positions(self):
        """Update all visual elements after zoom/pan change"""
        # Update grid
        self.draw_grid()
        
        # Update all people
        for person_id in list(self.person_widgets.keys()):
            self.refresh_person_widget(person_id)
        
        # Update all connections
        for (id1, id2) in list(self.connection_lines.keys()):
            if id1 in self.app.people and id2 in self.app.people:
                label = self.app.people[id1].connections.get(id2, "")
                if label:
                    self.draw_connection(id1, id2, label)
    
    def set_zoom(self, zoom):
        """Set zoom level and update display"""
        self.zoom_level = max(0.1, min(3.0, zoom))
        self.update_all_positions()
    
    def clear_all(self):
        """Clear all visual elements"""
        self.canvas.delete("all")
        self.person_widgets.clear()
        self.connection_lines.clear()
        self.draw_grid()
    
    # Event handlers
    def on_left_click(self, event):
        """Handle left mouse button click"""
        # Find clicked item
        item = self.canvas.find_closest(event.x, event.y)
        if not item:
            return
        
        tags = self.canvas.gettags(item[0])
        
        # Check if clicked on a person
        for tag in tags:
            if tag.startswith("person_"):
                person_id = int(tag.split("_")[1])
                self.selected_person = person_id
                self.dragging = True
                self.drag_start = {"x": event.x, "y": event.y}
                self.canvas.focus_set()
                logger.info(f"Selected person {person_id} for dragging")
                return
        
        # Check if clicked on a connection
        for tag in tags:
            if tag.startswith("connection_"):
                parts = tag.split("_")
                if len(parts) >= 3:
                    id1, id2 = int(parts[1]), int(parts[2])
                    self.selected_connection = (id1, id2)
                    self.canvas.focus_set()
                    return
    
    def on_drag(self, event):
        """Handle mouse drag"""
        if self.dragging and self.selected_person:
            # Calculate movement in screen space
            dx = event.x - self.drag_start["x"]
            dy = event.y - self.drag_start["y"]
            
            # Convert to world space movement
            dx_world = dx / self.zoom_level
            dy_world = dy / self.zoom_level
            
            # Update person position
            person = self.app.people[self.selected_person]
            person.x += dx_world
            person.y += dy_world
            
            # Update drag start position
            self.drag_start = {"x": event.x, "y": event.y}
            
            # Refresh display
            self.refresh_person_widget(self.selected_person)
            self.update_person_connections(self.selected_person)
            
            # Update connections from other people to this person
            for other_id, other_person in self.app.people.items():
                if self.selected_person in other_person.connections:
                    self.update_connection_line(other_id, self.selected_person)
    
    def on_release(self, event):
        """Handle mouse button release"""
        self.dragging = False
        self.selected_person = None
    
    def on_right_click(self, event):
        """Handle right mouse button click"""
        # Find clicked item
        item = self.canvas.find_closest(event.x, event.y)
        if not item:
            self.cancel_connection()
            return
        
        tags = self.canvas.gettags(item[0])
        
        # Check if clicked on a person
        person_id = None
        for tag in tags:
            if tag.startswith("person_"):
                person_id = int(tag.split("_")[1])
                break
        
        if person_id is None:
            self.cancel_connection()
            return
        
        # Handle connection logic
        if not self.connecting:
            # Start new connection
            self.start_connection(person_id)
        elif self.connection_start == person_id:
            # Cancel if clicking same person
            self.cancel_connection()
        else:
            # Complete connection
            self.complete_connection(person_id)
    
    def on_double_click(self, event):
        """Handle double click"""
        # Find clicked item
        item = self.canvas.find_closest(event.x, event.y)
        if not item:
            return
        
        tags = self.canvas.gettags(item[0])
        
        # Check if clicked on a person
        for tag in tags:
            if tag.startswith("person_"):
                person_id = int(tag.split("_")[1])
                self.app.edit_person(person_id)
                return
        
        # Check if clicked on a connection
        for tag in tags:
            if tag.startswith("connection_"):
                parts = tag.split("_")
                if len(parts) >= 3:
                    id1, id2 = int(parts[1]), int(parts[2])
                    self.edit_connection(id1, id2)
                    return
    
    def on_mouse_move(self, event):
        """Handle mouse movement"""
        if self.connecting and self.temp_line:
            # Update temporary line
            p = self.app.people[self.connection_start]
            x1, y1 = self.world_to_screen(p.x, p.y)
            self.canvas.coords(self.temp_line, x1, y1, event.x, event.y)
    
    def on_middle_press(self, event):
        """Handle middle mouse button press"""
        self._pan_start = {"x": self.pan_offset["x"], "y": self.pan_offset["y"]}
        self._pan_start_mouse = {"x": event.x, "y": event.y}
    
    def on_middle_drag(self, event):
        """Handle middle mouse button drag for panning"""
        if hasattr(self, '_pan_start_mouse'):
            # Calculate the difference from start position
            dx = event.x - self._pan_start_mouse["x"]
            dy = event.y - self._pan_start_mouse["y"]
            
            # Update pan offset
            self.pan_offset["x"] = self._pan_start["x"] + dx
            self.pan_offset["y"] = self._pan_start["y"] + dy
            
            # Update display
            self.update_all_positions()
    
    def on_middle_release(self, event):
        """Handle middle mouse button release"""
        pass
    
    def on_mouse_wheel(self, event):
        """Handle mouse wheel for zooming"""
        # Calculate zoom factor
        if event.delta > 0:
            factor = 1.1
        else:
            factor = 0.9
        
        # Get mouse position in world coordinates before zoom
        mouse_x = event.x - self.pan_offset["x"]
        mouse_y = event.y - self.pan_offset["y"]
        world_x = mouse_x / self.zoom_level
        world_y = mouse_y / self.zoom_level
        
        # Apply zoom
        self.zoom_level *= factor
        self.zoom_level = max(0.1, min(3.0, self.zoom_level))
        
        # Calculate new mouse position after zoom
        new_mouse_x = world_x * self.zoom_level
        new_mouse_y = world_y * self.zoom_level
        
        # Adjust pan to keep mouse position fixed
        self.pan_offset["x"] += mouse_x - new_mouse_x
        self.pan_offset["y"] += mouse_y - new_mouse_y
        
        # Update display
        self.update_all_positions()
        
        # Update zoom slider
        self.app.ui_manager.update_zoom_slider(self.zoom_level)
    
    def on_escape(self, event):
        """Handle escape key"""
        if self.connecting:
            self.cancel_connection()
    
    def on_delete(self, event):
        """Handle delete key"""
        if self.selected_connection:
            id1, id2 = self.selected_connection
            self.remove_connection(id1, id2)
            self.selected_connection = None
            self.app.ui_manager.update_status("Connection deleted")
        elif self.selected_person:
            self.app.delete_person(self.selected_person)
    
    # Connection management
    def start_connection(self, person_id):
        """Start creating a connection"""
        self.connecting = True
        self.connection_start = person_id
        
        # Create temporary line
        p = self.app.people[person_id]
        x, y = self.world_to_screen(p.x, p.y)
        
        self.temp_line = self.canvas.create_line(
            x, y, x, y,
            fill=COLORS['accent'],
            width=3,
            dash=(5, 5),
            tags="temp_line"
        )
        
        # Update status
        self.app.ui_manager.update_status(f"Connecting from {p.name} - right-click target person")
    
    def complete_connection(self, target_id):
        """Complete the connection"""
        if self.connecting and self.connection_start:
            self.create_connection(self.connection_start, target_id)
            self.cancel_connection()
    
    def cancel_connection(self):
        """Cancel current connection"""
        self.connecting = False
        self.connection_start = None
        
        if self.temp_line:
            self.canvas.delete(self.temp_line)
            self.temp_line = None
        
        self.app.ui_manager.update_status("Ready")
    
    def edit_connection(self, id1, id2):
        """Edit connection label"""
        key = (min(id1, id2), max(id1, id2))
        
        # Get current label
        current_label = self.app.people[id1].connections.get(id2, "")
        
        # Show dialog
        dialog = ConnectionLabelDialog(
            self.app.root, 
            "Edit Connection Label",
            current_label=current_label
        )
        self.app.root.wait_window(dialog.dialog)
        
        if dialog.result:
            # Update data model
            self.app.people[id1].connections[id2] = dialog.result
            self.app.people[id2].connections[id1] = dialog.result
            
            # Redraw connection
            self.draw_connection(id1, id2, dialog.result)
            
            self.app.ui_manager.update_status("Connection updated")