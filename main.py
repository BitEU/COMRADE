import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import csv
import math
from datetime import datetime
import os
from collections import defaultdict
import logging

# Import from supporting modules
from constants import COLORS
from models import Person
from dialogs import PersonDialog, ConnectionLabelDialog

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConnectionApp:
    def __init__(self, root):
        logger.info("Initializing ConnectionApp")
        self.root = root
        self.root.title("🔗 People Connection Visualizer")
        self.root.geometry("1400x900")
        self.root.configure(bg=COLORS['background'])
        
        # Configure modern styling
        self.setup_styles()        # Data structures
        self.people = {}  # {id: Person}
        self.person_widgets = {}  # {id: canvas_item_id}
        self.connection_lines = {}  # {(id1, id2): (line_id, label_id)}
        self.selected_person = None
        self.selected_connection = None  # Track selected connection for editing/deletion
        self.dragging = False
        self.drag_data = {"x": 0, "y": 0}
        self.connecting = False
        self.connection_start = None
        self.temp_line = None
        self.next_id = 1
        
        logger.info("Setting up UI")
        self.setup_ui()
        logger.info("ConnectionApp initialized successfully")
    
    def setup_styles(self):
        """Configure modern ttk styles"""
        style = ttk.Style()
        
        # Configure button style
        style.configure(
            "Modern.TButton",
            font=("Segoe UI", 10),
            padding=(15, 8)
        )
        
        # Configure frame style
        style.configure(
            "Modern.TFrame",
            background=COLORS['surface']
        )
        
        # Configure label style
        style.configure(
            "Modern.TLabel",
            font=("Segoe UI", 10),
            background=COLORS['surface'],
            foreground=COLORS['text_primary']
        )
        
        # Configure entry style
        style.configure(
            "Modern.TEntry",
            font=("Segoe UI", 10),
            fieldbackground=COLORS['surface']
        )
        
    def setup_ui(self):
        # Create main container
        main_container = ttk.Frame(self.root, style="Modern.TFrame")
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Header section
        header_frame = ttk.Frame(main_container, style="Modern.TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Title
        title_label = ttk.Label(header_frame, text="People Connection Visualizer", 
                               font=("Segoe UI", 20, "bold"), 
                               foreground=COLORS['primary'], 
                               style="Modern.TLabel")
        title_label.pack(side=tk.LEFT)
        
        # Toolbar with modern buttons
        toolbar = ttk.Frame(main_container, style="Modern.TFrame")
        toolbar.pack(fill=tk.X, pady=(0, 15))
          # Create modern buttons with icons
        self.create_modern_button(toolbar, "👤 Add Person", self.add_person, COLORS['primary'])
        self.create_modern_button(toolbar, "💾 Save", self.save_data, COLORS['accent'])
        self.create_modern_button(toolbar, "📁 Load", self.load_data, COLORS['accent'])
        self.create_modern_button(toolbar, "🗑️ Clear All", self.clear_all, COLORS['danger'])
        
        # Canvas container with modern styling
        canvas_frame = ttk.Frame(main_container, style="Modern.TFrame")
        canvas_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Modern canvas with gradient-like background
        self.canvas = tk.Canvas(canvas_frame, 
                               bg='#f8fafc', 
                               highlightthickness=0,
                               relief=tk.FLAT,
                               bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Add subtle grid pattern to canvas
        self.add_grid_pattern()        # Bind events
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-2>", self.on_middle_button_press)
        self.canvas.bind("<B2-Motion>", self.on_middle_button_motion)
        self.canvas.bind("<ButtonRelease-2>", self.on_middle_button_release)
        # Add mouse wheel zoom support
        self.canvas.bind("<MouseWheel>", self.on_canvas_zoom)
          # Make canvas focusable and bind keys
        self.canvas.configure(highlightthickness=1, highlightcolor=COLORS['primary'])
        self.canvas.bind("<Key-Escape>", self.on_escape_key)
        self.canvas.bind("<Key-Delete>", self.on_delete_key)
        self.canvas.bind("<Key-BackSpace>", self.on_delete_key)  # Also bind backspace
        self.root.bind("<Key-Escape>", self.on_escape_key)  # Also bind to root for global access
        self.root.bind("<Key-Delete>", self.on_delete_key)
        self.root.bind("<Key-BackSpace>", self.on_delete_key)
          # Modern instructions panel
        self.create_instructions_panel(main_container)
        
        # Status bar
        self.status_frame = ttk.Frame(main_container, style="Modern.TFrame")
        self.status_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.status_label = ttk.Label(self.status_frame, 
                                    text="Ready - Right-click a person to start linking",
                                    font=("Segoe UI", 9),
                                    foreground=COLORS['text_secondary'],
                                    style="Modern.TLabel")
        self.status_label.pack(side=tk.LEFT)

        # --- Zoom slider ---
        self.zoom_var = tk.DoubleVar(value=1.0)
        self.zoom_slider = ttk.Scale(
            self.status_frame,
            from_=0.5, to=1.0, orient=tk.HORIZONTAL,
            variable=self.zoom_var,
            command=self.on_zoom,
            length=150
        )
        self.zoom_slider.pack(side=tk.RIGHT, padx=(0, 10))
        self.zoom_label = ttk.Label(self.status_frame, text="Zoom", style="Modern.TLabel")
        self.zoom_label.pack(side=tk.RIGHT)
        
        # Bind canvas resize event
        self.canvas.bind('<Configure>', self.on_canvas_resize)
    
    def on_zoom(self, value):
        # Scale the canvas content based on the zoom value
        try:
            zoom = float(value)
        except ValueError:
            zoom = 1.0
        # Reset scale, then apply new scale
        self.canvas.scale("all", 0, 0, 1/self._last_zoom if hasattr(self, '_last_zoom') else 1, 1/self._last_zoom if hasattr(self, '_last_zoom') else 1)
        self.canvas.scale("all", 0, 0, zoom, zoom)
        self._last_zoom = zoom
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.rescale_text(zoom)
        self.redraw_grid()

    def rescale_text(self, zoom):
        # Rescale all text items on the canvas
        for item in self.canvas.find_all():
            if self.canvas.type(item) == 'text':
                current_font = self.canvas.itemcget(item, 'font')
                # Parse font string: e.g., 'Segoe UI 10 bold'
                parts = current_font.split()
                # Find the first integer in the font string (the size)
                base_size = None
                for i, part in enumerate(parts):
                    if part.isdigit():
                        base_size = int(part)
                        size_index = i
                        break
                if base_size is not None:
                    new_size = max(6, int(base_size * zoom))
                    # Rebuild font string with new size
                    new_font = ' '.join(parts[:size_index] + [str(new_size)] + parts[size_index+1:])
                else:
                    # fallback: just set size
                    new_font = f"Segoe UI {int(10 * zoom)}"
                self.canvas.itemconfig(item, font=new_font)

    def on_canvas_resize(self, event):
        self.redraw_grid()

    def redraw_grid(self):
        # Remove old grid
        self.canvas.delete("grid")
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        grid_size = 40 * (self._last_zoom if hasattr(self, '_last_zoom') else 1)
        for x in range(0, int(width + grid_size), int(grid_size)):
            self.canvas.create_line(x, 0, x, height, fill='#e2e8f0', width=1, tags="grid")
        for y in range(0, int(height + grid_size), int(grid_size)):
            self.canvas.create_line(0, y, width, y, fill='#e2e8f0', width=1, tags="grid")
        self.canvas.tag_lower("grid")
    
    def create_modern_button(self, parent, text, command, color):
        """Create a modern styled button"""
        btn = tk.Button(parent, 
                       text=text,
                       command=command,
                       font=("Segoe UI", 10, "bold"),
                       bg=color,
                       fg='white',
                       relief=tk.FLAT,
                       padx=20,
                       pady=10,
                       cursor='hand2',
                       border=0)
        
        # Add hover effects
        def on_enter(e):
            btn.configure(bg=self.darken_color(color))
        
        def on_leave(e):
            btn.configure(bg=color)
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        btn.pack(side=tk.LEFT, padx=(0, 10))
        return btn
    
    def darken_color(self, color):
        """Darken a hex color by 20%"""
        color = color.lstrip('#')
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        darkened = tuple(int(c * 0.8) for c in rgb)
        return '#%02x%02x%02x' % darkened
    
    def add_grid_pattern(self):
        """Add a subtle grid pattern to the canvas"""
        canvas_width = 1400
        canvas_height = 900
        grid_size = 40
        
        # Vertical lines
        for x in range(0, canvas_width, grid_size):
            self.canvas.create_line(x, 0, x, canvas_height, 
                                  fill='#e2e8f0', width=1, tags="grid")
        
        # Horizontal lines
        for y in range(0, canvas_height, grid_size):
            self.canvas.create_line(0, y, canvas_width, y, 
                                  fill='#e2e8f0', width=1, tags="grid")
        
        # Send grid to back
        self.canvas.tag_lower("grid")
    
    def create_instructions_panel(self, parent):
        """Create a modern instructions panel"""
        instructions_frame = ttk.Frame(parent, style="Modern.TFrame")
        instructions_frame.pack(fill=tk.X, pady=(10, 0))
          # Instructions with modern styling
        instructions = [
            "🖱️ Left-click to select and move people",
            "� Right-click to link: first person, then target", 
            "✏️ Double-click on a person to edit their information",            "⌨️ Press Escape to cancel an active connection"
        ]
        
        for i, instruction in enumerate(instructions):
            label = ttk.Label(instructions_frame, 
                            text=instruction,
                            font=("Segoe UI", 9),
                            foreground=COLORS['text_secondary'],
                            style="Modern.TLabel")
            label.pack(side=tk.LEFT, padx=(0, 20) if i < len(instructions)-1 else (0, 0))
        
    def add_person(self):
        logger.info("Add person button clicked")
        dialog = PersonDialog(self.root, "Add Person")
        self.root.wait_window(dialog.dialog)  # Wait for dialog to close
        logger.info(f"Dialog result: {dialog.result}")
        if dialog.result:
            person = Person(**dialog.result)
            person_id = self.next_id
            self.next_id += 1
            logger.info(f"Creating person with ID {person_id}: {person.name}")
            
            # Position using box layout
            cols = 2
            col_width = 400
            row_height = 200
            start_x = 200
            start_y = 120
            row = (len(self.people)) // cols
            col = (len(self.people)) % cols
            person.x = start_x + col * col_width
            person.y = start_y + row * row_height
            logger.info(f"Positioned person at ({person.x}, {person.y})")
            
            self.people[person_id] = person
            logger.info(f"Added person to data structure. Total people: {len(self.people)}")
            self.create_person_widget(person_id)
            logger.info(f"Created widget for person {person_id}")
        else:
            logger.info("Dialog was cancelled")
            
    def create_person_widget(self, person_id, zoom=None):
        logger.info(f"Creating modern widget for person {person_id}")
        person = self.people[person_id]
        if zoom is None:
            zoom = self._last_zoom if hasattr(self, '_last_zoom') else 1.0
        # Store base positions if not already present
        if not hasattr(person, 'base_x'):
            person.base_x = person.x
            person.base_y = person.y
        x = person.x * zoom
        y = person.y * zoom
        logger.info(f"Widget position: ({x}, {y})")
        
        # Create group
        group = []
        
        # Calculate text dimensions
        info_lines = [
            f"👤 {person.name}" if person.name else "👤 Unnamed",
            f"🎂 {person.dob}" if person.dob else "",
            f"🏷️ {person.alias}" if person.alias else "",
            f"🏠 {person.address}" if person.address else "",
            f"📞 {person.phone}" if person.phone else ""
        ]
        
        # Filter out empty lines
        info_lines = [line for line in info_lines if line.strip()]
        
        # Calculate modern card dimensions
        card_width = max(max(len(line) for line in info_lines) * 9, 200) * zoom
        card_height = max(len(info_lines) * 25 + 40, 120) * zoom
        
        half_width = card_width // 2
        half_height = card_height // 2
        
        logger.info(f"Calculated modern card dimensions: {card_width}x{card_height}")
          # Create shadow effect (multiple rectangles with offset)
        shadow_offset = int(3 * zoom)
        for i in range(3, 0, -1):
            # Use progressively lighter gray colors for shadow effect
            shadow_color = '#e0e0e0' if i == 3 else ('#d0d0d0' if i == 2 else '#c0c0c0')
            
            shadow = self.canvas.create_rectangle(
                x - half_width + i, y - half_height + i,
                x + half_width + i, y + half_height + i,
                fill=shadow_color, outline='', width=0,
                tags=(f"person_{person_id}", "person", "shadow")
            )
            group.append(shadow)
        
        # Main card background with gradient effect
        main_card = self.canvas.create_rectangle(
            x - half_width, y - half_height,
            x + half_width, y + half_height,
            fill=COLORS['surface'], 
            outline=COLORS['primary'], 
            width=2,
            tags=(f"person_{person_id}", "person")
        )
        group.append(main_card)
        
        # Header section with accent color
        header_height = int(30 * zoom)
        header = self.canvas.create_rectangle(
            x - half_width, y - half_height,
            x + half_width, y - half_height + header_height,
            fill=COLORS['primary'], outline='', width=0,
            tags=(f"person_{person_id}", "person")
        )
        group.append(header)
        
        # Person avatar (modern circular design)
        avatar_size = int(20 * zoom)
        avatar_x = x - half_width + int(15 * zoom)
        avatar_y = y - half_height + int(15 * zoom)
        
        # Avatar background
        avatar_bg = self.canvas.create_oval(
            avatar_x - avatar_size//2, avatar_y - avatar_size//2,
            avatar_x + avatar_size//2, avatar_y + avatar_size//2,
            fill='white', outline=COLORS['primary_light'], width=2,
            tags=(f"person_{person_id}", "person")
        )
        group.append(avatar_bg)
        
        # Avatar icon
        avatar_icon = self.canvas.create_text(
            avatar_x, avatar_y, text="👤",
            font=("Arial", int(10 * zoom)), fill=COLORS['primary'],
            tags=(f"person_{person_id}", "person")
        )
        group.append(avatar_icon)
        
        # Name in header (white text)
        name_text = self.canvas.create_text(
            avatar_x + avatar_size + int(10 * zoom), avatar_y,
            text=person.name or "Unnamed",
            anchor="w", font=("Segoe UI", int(11 * zoom), "bold"), 
            fill='white',
            tags=(f"person_{person_id}", "person")
        )
        group.append(name_text)
        
        # Details section
        details_start_y = y - half_height + header_height + int(15 * zoom)
        line_height = int(20 * zoom)
        
        details = [
            ("🎂", person.dob),
            ("🏷️", person.alias),
            ("🏠", person.address),
            ("📞", person.phone)
        ]
        current_y = details_start_y
        icon_x = x - half_width + int(15 * zoom)
        text_x = icon_x + int(25 * zoom)  # Space between icon and text
        for icon, value in details:
            if value and value.strip():
                icon_item = self.canvas.create_text(
                    icon_x, current_y,
                    text=icon,
                    anchor="nw", font=("Segoe UI Emoji", int(9 * zoom)),
                    fill=COLORS['text_primary'],
                    tags=(f"person_{person_id}", "person")
                )
                text_item = self.canvas.create_text(
                    text_x, current_y,
                    text=value,
                    anchor="nw", font=("Segoe UI", int(9 * zoom)),
                    fill=COLORS['text_primary'],
                    tags=(f"person_{person_id}", "person")
                )
                group.extend([icon_item, text_item])
                current_y += line_height
        
        # Add subtle border radius effect (visual enhancement)
        corner_size = int(4 * zoom)
        corners = [
            # Top-left
            (x - half_width, y - half_height, x - half_width + corner_size, y - half_height + corner_size),
            # Top-right  
            (x + half_width - corner_size, y - half_height, x + half_width, y - half_height + corner_size),
            # Bottom-left
            (x - half_width, y + half_height - corner_size, x - half_width + corner_size, y + half_height),
            # Bottom-right
            (x + half_width - corner_size, y + half_height - corner_size, x + half_width, y + half_height)
        ]
        
        for corner_coords in corners:
            corner = self.canvas.create_oval(
                *corner_coords,
                fill=COLORS['surface'], outline='', width=0,
                tags=(f"person_{person_id}", "person", "corner")
            )
            group.append(corner)
        
        self.person_widgets[person_id] = group
        logger.info(f"Created modern widget group for person {person_id}")
        
        # Bind double-click for editing
        for item in group:
            self.canvas.tag_bind(item, "<Double-Button-1>", lambda e, pid=person_id: self.edit_person(pid))
          # Add hover effects
        self.add_hover_effects(person_id, group)
        
        logger.info(f"Modern widget creation complete for person {person_id}")
    
    def add_hover_effects(self, person_id, group):
        """Add subtle hover effects to person widgets that preserve text readability"""
        def on_enter(event):
            # Don't apply hover if this person is selected for connecting
            if self.connecting and self.connection_start == person_id:
                return
                
            # Subtle border highlight effect on hover - no background color changes
            for item in group:
                if 'shadow' not in self.canvas.gettags(item) and 'corner' not in self.canvas.gettags(item):
                    try:
                        # Only highlight borders/outlines, not backgrounds
                        if self.canvas.type(item) == 'rectangle':
                            self.canvas.itemconfig(item, outline=COLORS['primary'], width=2)
                    except:
                        pass
        
        def on_leave(event):
            # Don't remove hover if this person is selected for connecting
            if self.connecting and self.connection_start == person_id:
                return
                
            # Remove border highlight
            for item in group:
                if 'shadow' not in self.canvas.gettags(item) and 'corner' not in self.canvas.gettags(item):
                    try:
                        if self.canvas.type(item) == 'rectangle':
                            self.canvas.itemconfig(item, outline=COLORS['border'], width=1)
                    except:
                        pass
        
        for item in group:
            self.canvas.tag_bind(item, "<Enter>", on_enter)
            self.canvas.tag_bind(item, "<Leave>", on_leave)
    
    def highlight_person_for_connection(self, person_id):
        """Highlight a person card to show it's selected for connection"""
        group = self.person_widgets[person_id]
        for item in group:
            if 'shadow' not in self.canvas.gettags(item) and 'corner' not in self.canvas.gettags(item):
                try:
                    current_fill = self.canvas.itemcget(item, 'fill')
                    if current_fill == COLORS['surface']:
                        self.canvas.itemconfig(item, fill='#4a5568')  # Dark gray
                    elif current_fill == COLORS['primary']:
                        self.canvas.itemconfig(item, fill='#2d3748')  # Darker header
                except:
                    pass
        
        # Update text colors for better contrast
        for item in group:
            try:
                if self.canvas.type(item) == 'text':
                    current_fill = self.canvas.itemcget(item, 'fill')
                    if current_fill == COLORS['text_primary']:
                        self.canvas.itemconfig(item, fill='white')
            except:
                pass
    
    def unhighlight_person_for_connection(self, person_id):
        """Remove highlight from a person card"""
        group = self.person_widgets[person_id]
        for item in group:
            if 'shadow' not in self.canvas.gettags(item) and 'corner' not in self.canvas.gettags(item):
                try:
                    current_fill = self.canvas.itemcget(item, 'fill')
                    if current_fill == '#4a5568':  # Dark gray
                        self.canvas.itemconfig(item, fill=COLORS['surface'])
                    elif current_fill == '#2d3748':  # Darker header
                        self.canvas.itemconfig(item, fill=COLORS['primary'])
                except:
                    pass            # Restore text colors
            for item in group:
                try:
                    if self.canvas.type(item) == 'text':
                        current_fill = self.canvas.itemcget(item, 'fill')
                        if current_fill == 'white' and 'shadow' not in self.canvas.gettags(item):
                            # Check if it's header text (should stay white) or body text
                            item_tags = self.canvas.gettags(item)
                            coords = self.canvas.coords(item)
                            if len(coords) >= 2:
                                # Get the text content to identify header vs body text
                                text_content = self.canvas.itemcget(item, 'text')
                                person = self.people[person_id]
                                  # Only header text (person name and avatar icon) should stay white
                                # Body text (birthday, alias, address, phone) should be restored to primary color
                                if text_content == person.name or text_content == "👤":
                                    # Keep white for header text
                                    pass
                                else:
                                    # Restore primary color for body text
                                    self.canvas.itemconfig(item, fill=COLORS['text_primary'])
                except:
                    pass
            
    def on_canvas_click(self, event):
        # Account for zoom in hit detection
        zoom = self._last_zoom if hasattr(self, '_last_zoom') else 1.0
        tolerance = 3  # Small area around the cursor
        
        # Use canvas coordinates directly for hit detection
        items = self.canvas.find_overlapping(event.x - tolerance, event.y - tolerance, event.x + tolerance, event.y + tolerance)
        if not items:
            return
            
        # Clear previous selections
        self.clear_connection_selection()
        
        # Find the topmost person item under the cursor
        selected_person_id = None
        for item in reversed(items):  # reversed: topmost first
            tags = self.canvas.gettags(item)
            if any("person" in tag for tag in tags):
                for tag in tags:
                    if tag.startswith("person_"):
                        selected_person_id = int(tag.split("_")[1])
                        break
                if selected_person_id is not None:
                    break
        
        if selected_person_id is not None:
            # Normalize all widgets to current zoom level before starting drag
            # This ensures consistent interaction regardless of how zoom was applied
            self.normalize_all_widgets_to_current_zoom()
            
            self.selected_person = selected_person_id
            self.drag_data = {"x": event.x, "y": event.y}
            self.dragging = True
        else:
            # Check for connection selection as before
            for item in items:
                tags = self.canvas.gettags(item)
                if any("connection_" in tag for tag in tags):
                    for tag in tags:
                        if tag.startswith("connection_label_") or tag.startswith("connection_clickable_"):
                            parts = tag.split("_")
                            if len(parts) >= 4:
                                id1, id2 = int(parts[2]), int(parts[3])
                                self.selected_connection = (min(id1, id2), max(id1, id2))
                                self.highlight_connection_selection()
                                self.canvas.focus_set()
                                break
                    break

    def on_canvas_drag(self, event):
        if self.dragging and self.selected_person:
            zoom = self._last_zoom if hasattr(self, '_last_zoom') else 1.0
            
            # Calculate the movement delta in screen coordinates
            dx_screen = event.x - self.drag_data["x"]
            dy_screen = event.y - self.drag_data["y"]
            
            # Convert screen delta to world delta (compensate for zoom)
            dx_world = dx_screen / zoom
            dy_world = dy_screen / zoom
            
            logger.debug(f"[DRAG] Zoom: {zoom:.3f}, Mouse: ({event.x}, {event.y}), "
                         f"Screen Δ: ({dx_screen}, {dy_screen}), World Δ: ({dx_world:.2f}, {dy_world:.2f})")

            # Update logical (unscaled) position using world delta
            self.people[self.selected_person].x += dx_world
            self.people[self.selected_person].y += dy_world
            logger.debug(f"[DRAG] Updated logical position: ({self.people[self.selected_person].x}, {self.people[self.selected_person].y})")

            # Move existing canvas items directly during drag (much more efficient)
            person_items = self.person_widgets[self.selected_person]
            for item in person_items:
                self.canvas.move(item, dx_screen, dy_screen)

            # Update connections immediately (but efficiently)
            self.update_connections()            # Update drag data for next movement
            self.drag_data = {"x": event.x, "y": event.y}

    def on_canvas_release(self, event):
        if self.dragging and self.selected_person:
            # After dragging is complete, refresh the widget to ensure correct positioning
            # This normalizes the widget to the correct zoom level
            self.refresh_person_widget(self.selected_person)
        self.dragging = False
    
    def on_double_click(self, event):
        """Handle double-click events for editing connections"""
        items = self.canvas.find_closest(event.x, event.y)
        if not items:
            return
            
        clicked = items[0]
        tags = self.canvas.gettags(clicked)
        
        # Check if double-clicked on a connection label
        for tag in tags:
            if tag.startswith("connection_label_") or tag.startswith("connection_clickable_"):
                # Extract connection IDs from tag
                parts = tag.split("_")
                if len(parts) >= 4:
                    id1, id2 = int(parts[2]), int(parts[3])
                    self.selected_connection = (min(id1, id2), max(id1, id2))
                    self.edit_connection_label()
                    break
    
    def on_mouse_move(self, event):
        # Update hover effects using more forgiving detection
        # Use a small area around the cursor instead of just the closest point
        tolerance = 5  # pixels
        items = self.canvas.find_overlapping(event.x - tolerance, event.y - tolerance, 
                                           event.x + tolerance, event.y + tolerance)
        
        # Find if we're hovering over a person (look through all overlapping items)
        person_id = None
        for item in items:
            tags = self.canvas.gettags(item)
            if any("person" in tag for tag in tags):
                for tag in tags:
                    if tag.startswith("person_"):
                        person_id = int(tag.split("_")[1])
                        break
                if person_id is not None:
                    break
        
        # Apply hover effects only if not in connection mode or if hovering over different person
        if person_id is not None:
            if not self.connecting or (self.connecting and person_id != self.connection_start):
                # Use existing hover system but make it simpler
                if hasattr(self, 'current_hover') and self.current_hover != person_id:
                    self.remove_hover_from_person(self.current_hover)
                if not hasattr(self, 'current_hover') or self.current_hover != person_id:
                    self.apply_hover_to_person(person_id)
                    self.current_hover = person_id
        else:
            if hasattr(self, 'current_hover'):
                self.remove_hover_from_person(self.current_hover)
                delattr(self, 'current_hover')        # Update temp line if connecting - make it more responsive
        if self.connecting and self.temp_line and self.connection_start:
            p = self.people[self.connection_start]
            # Get the current zoom level
            zoom = self._last_zoom if hasattr(self, '_last_zoom') else 1.0
            # Update the temporary line to follow the mouse smoothly
            # The person position needs to be scaled to zoom factor
            start_x, start_y = p.x * zoom, p.y * zoom
            # Convert mouse coordinates to canvas coordinates to handle panning
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            self.canvas.coords(self.temp_line, start_x, start_y, canvas_x, canvas_y)
              # Change line color based on what we're hovering over
            if person_id is not None and person_id != self.connection_start:
                # Hovering over a different person - show ready to connect
                self.canvas.itemconfig(self.temp_line, fill=COLORS['success'], width=4)
            else:
                # Hovering over same person or empty space
                self.canvas.itemconfig(self.temp_line, fill=COLORS['accent'], width=3)
    
    def on_right_click(self, event):
        """Improved right-click linking with more forgiving detection"""
        tolerance = 10  # Larger tolerance for right-clicks
        items = self.canvas.find_overlapping(event.x - tolerance, event.y - tolerance, 
                                           event.x + tolerance, event.y + tolerance)
        logger.debug(f"Right-click at ({event.x}, {event.y}), found items: {items}")
        # Find the person that was clicked
        person_id = None
        for item in items:
            tags = self.canvas.gettags(item)
            logger.debug(f"Item {item} tags: {tags}")
            if any("person" in tag for tag in tags):
                for tag in tags:
                    if tag.startswith("person_"):
                        person_id = int(tag.split("_")[1])
                        logger.debug(f"Detected person_id {person_id} from tag {tag}")
                        break
                if person_id is not None:
                    break
        if person_id is None:
            logger.info("Right-click not on a person, cancelling connection if active.")
            # Not clicking on a person, cancel connection
            self.cancel_connection()
            return
        logger.info(f"Right-clicked person: {person_id} ({self.people[person_id].name})")
        # Handle the right-click on a person
        if not self.connecting:
            logger.info(f"No active connection. Starting new connection from {person_id} ({self.people[person_id].name})")
            # Start a new connection
            self.start_connection(person_id, event.x, event.y)
        elif self.connection_start == person_id:
            logger.info(f"Right-clicked the same person ({person_id}). Cancelling connection.")
            # Right-clicking on the same person cancels the connection
            self.cancel_connection()
        else:
            logger.info(f"Completing connection: {self.connection_start} ({self.people[self.connection_start].name}) -> {person_id} ({self.people[person_id].name})")
            # Right-clicking on a different person completes the connection
            self.complete_connection(person_id)
    
    def start_connection(self, person_id, x, y):
        """Start a new connection from the given person"""
        logger.info(f"[LINK] Starting connection from person {person_id} ({self.people[person_id].name}) at ({x}, {y})")
        self.connecting = True
        self.connection_start = person_id
        
        # Highlight the selected person
        self.highlight_person_for_connection(person_id)        # Show temporary line
        p = self.people[person_id]
        zoom = self._last_zoom if hasattr(self, '_last_zoom') else 1.0
        if self.temp_line:
            self.canvas.delete(self.temp_line)
        # Use scaled coordinates for the temp line
        start_x, start_y = p.x * zoom, p.y * zoom
        # Convert mouse coordinates to canvas coordinates to handle panning
        canvas_x = self.canvas.canvasx(x)
        canvas_y = self.canvas.canvasy(y)
        self.temp_line = self.canvas.create_line(start_x, start_y, canvas_x, canvas_y, 
                                               fill=COLORS['accent'], dash=(8, 4), width=3,
                                               tags=("temp_connection",))
          # Update status
        self.update_status(f"🔗 Linking from {self.people[person_id].name} - Right-click another person to connect")
    
    def complete_connection(self, target_id):
        """Complete the connection to the target person"""
        if not self.connecting or not self.connection_start:
            logger.warning("[LINK] Attempted to complete connection with no active start.")
            return
        logger.info(f"[LINK] Completing connection from {self.connection_start} ({self.people[self.connection_start].name}) to {target_id} ({self.people[target_id].name})")
        
        # Store the names before cleaning up
        from_name = self.people[self.connection_start].name
        to_name = self.people[target_id].name
        
        # Create the connection
        self.create_connection(self.connection_start, target_id)
        
        # Clean up connection state
        self.cancel_connection()
        
        # Update status
        self.update_status(f"✅ Connected {from_name} to {to_name}")
    
    def cancel_connection(self):
        """Cancel any active connection"""
        if self.connecting and self.connection_start:
            logger.info(f"[LINK] Cancelling connection from person {self.connection_start} ({self.people[self.connection_start].name})")
            self.unhighlight_person_for_connection(self.connection_start)
            self.update_status("Connection cancelled")
        else:
            logger.info("[LINK] No active connection to cancel.")
        self.connecting = False
        self.connection_start = None
        
        if self.temp_line:
            self.canvas.delete(self.temp_line)
            self.temp_line = None
    
    def create_connection(self, id1, id2):
        # Check if connection already exists
        if id2 in self.people[id1].connections:
            logger.warning(f"[LINK] Connection already exists between {id1} ({self.people[id1].name}) and {id2} ({self.people[id2].name}). Aborting.")
            return
        logger.info(f"[LINK] Creating connection from {id1} ({self.people[id1].name}) to {id2} ({self.people[id2].name})")
        # Ask for label using modern dialog
        dialog = ConnectionLabelDialog(self.root, "Add Connection")
        dialog.dialog.wait_window()  # Wait for dialog to close
        if dialog.result is None:
            logger.info(f"[LINK] Connection label dialog cancelled for {id1} -> {id2}")
            return
        label = dialog.result
        logger.info(f"[LINK] Assigned label '{label}' to connection {id1} ({self.people[id1].name}) <-> {id2} ({self.people[id2].name})")
        # Add to data structure
        self.people[id1].connections[id2] = label
        self.people[id2].connections[id1] = label
        # Draw line
        self.draw_connection(id1, id2, label)
        
    def draw_connection(self, id1, id2, label, zoom=None):
        if zoom is None:
            zoom = self._last_zoom if hasattr(self, '_last_zoom') else 1.0
        p1 = self.people[id1]
        p2 = self.people[id2]
        x1, y1 = p1.x * zoom, p1.y * zoom
        x2, y2 = p2.x * zoom, p2.y * zoom
        line = self.canvas.create_line(x1, y1, x2, y2, 
                                     fill=COLORS['secondary'], 
                                     width=3,
                                     smooth=True,
                                     tags=("connection",))
        shadow_line = self.canvas.create_line(x1+1, y1+1, x2+1, y2+1, 
                                            fill='#CCCCCC', 
                                            width=3,
                                            smooth=True,
                                            tags=("connection", "shadow"))
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        label_width = max(len(label) * 8, 60) * zoom
        label_height = 28 * zoom
        padding = 15 * zoom
        box_width = label_width + padding * 2
        box_height = label_height + 8 * zoom
        half_width = box_width / 2
        half_height = box_height / 2
        logger.info(f"Modern connection label '{label}' - calculated box: {box_width}x{box_height}")
        label_shadow = self.canvas.create_rectangle(
            mid_x - half_width + 2, mid_y - half_height + 2, 
            mid_x + half_width + 2, mid_y + half_height + 2,
            fill='#000015', outline='', width=0,
            tags=("connection", "shadow"))
        label_bg = self.canvas.create_rectangle(
            mid_x - half_width, mid_y - half_height, 
            mid_x + half_width, mid_y + half_height,
            fill=COLORS['surface'], 
            outline=COLORS['secondary'], 
            width=2,
            tags=("connection",))
        icon = "🔗"
        if "family" in label.lower() or "parent" in label.lower() or "child" in label.lower():
            icon = "👨‍👩‍👧‍👦"
        elif "friend" in label.lower():
            icon = "👫"
        elif "work" in label.lower() or "colleague" in label.lower():
            icon = "💼"
        elif "partner" in label.lower() or "spouse" in label.lower():
            icon = "💑"
        icon_text = self.canvas.create_text(
            mid_x - half_width + int(15 * zoom), mid_y,
            text=icon,
            font=("Arial", int(12 * zoom)),
            tags=("connection",))
        label_text = self.canvas.create_text(
            mid_x, mid_y,
            text=label,
            font=("Segoe UI", int(10 * zoom)),
            tags=("connection", f"connection_label_{min(id1, id2)}_{max(id1, id2)}"))
        
        # Make label clickable by adding larger invisible area
        clickable_area = self.canvas.create_rectangle(
            mid_x - half_width, mid_y - half_height, 
            mid_x + half_width, mid_y + half_height,
            fill="", outline="", width=0,
            tags=("connection", f"connection_clickable_{min(id1, id2)}_{max(id1, id2)}"))
        
        # Store connection info with all elements
        key = (min(id1, id2), max(id1, id2))
        self.connection_lines[key] = (shadow_line, line, label_shadow, label_bg, icon_text, label_text, clickable_area)
        
        # Move connections to back but labels to front
        self.canvas.tag_lower(shadow_line)
        self.canvas.tag_lower(line)
        self.canvas.tag_raise(label_shadow)
        self.canvas.tag_raise(label_bg)
        self.canvas.tag_raise(icon_text)
        self.canvas.tag_raise(label_text)
        
    def update_connections(self):
        zoom = self._last_zoom if hasattr(self, '_last_zoom') else 1.0
        # Redraw all modern connections
        for (id1, id2), elements in self.connection_lines.items():
            if len(elements) >= 7:  # New format with 7 elements
                shadow_line, line, label_shadow, label_bg, icon_text, label_text, clickable_area = elements

                p1 = self.people[id1]
                p2 = self.people[id2]
                x1, y1 = p1.x * zoom, p1.y * zoom
                x2, y2 = p2.x * zoom, p2.y * zoom

                # Update shadow line
                self.canvas.coords(shadow_line, x1+1, y1+1, x2+1, y2+1)
                # Update main line
                self.canvas.coords(line, x1, y1, x2, y2)

                # Update label position
                mid_x = (x1 + x2) / 2
                mid_y = (y1 + y2) / 2
                label = self.canvas.itemcget(label_text, "text")
                label_width = max(len(label) * 8, 60) * zoom
                label_height = 28 * zoom
                padding = 15 * zoom
                box_width = label_width + padding * 2
                box_height = label_height + 8 * zoom
                half_width = box_width / 2
                half_height = box_height / 2
                self.canvas.coords(label_shadow, 
                                 mid_x - half_width + 2, mid_y - half_height + 2, 
                                 mid_x + half_width + 2, mid_y + half_height + 2)
                self.canvas.coords(label_bg, 
                                 mid_x - half_width, mid_y - half_height, 
                                 mid_x + half_width, mid_y + half_height)
                self.canvas.coords(icon_text, mid_x - half_width + int(15 * zoom), mid_y)
                self.canvas.coords(label_text, mid_x, mid_y)
                self.canvas.coords(clickable_area,
                                 mid_x - half_width, mid_y - half_height, 
                                 mid_x + half_width, mid_y + half_height)
            else:
                # Handle old format connections (fallback)
                line, label_bg, label_text = elements[:3]
                p1 = self.people[id1]
                p2 = self.people[id2]
                x1, y1 = p1.x * zoom, p1.y * zoom
                x2, y2 = p2.x * zoom, p2.y * zoom
                self.canvas.coords(line, x1, y1, x2, y2)
                mid_x = (x1 + x2) / 2
                mid_y = (y1 + y2) / 2
                self.canvas.coords(label_bg, mid_x - 30, mid_y - 10, mid_x + 30, mid_y + 10)
                self.canvas.coords(label_text, mid_x, mid_y)
            
    def edit_person(self, person_id):
        person = self.people[person_id]
        dialog = PersonDialog(self.root, "Edit Person", 
                            name=person.name, dob=person.dob, 
                            alias=person.alias, address=person.address, 
                            phone=person.phone)
        if dialog.result:
            # Update person data
            for key, value in dialog.result.items():
                setattr(person, key, value)
            
            # Update display
            self.refresh_person_widget(person_id)
            
    def refresh_person_widget(self, person_id):
        # Delete old widget
        for item in self.person_widgets[person_id]:
            self.canvas.delete(item)
            
        # Create new widget
        self.create_person_widget(person_id)
          # Restore connections to back
        self.canvas.tag_lower("connection")
        
    def apply_box_layout(self):
        cols = 2  # Reduce to 2 columns for larger boxes
        col_width = 400  # Increase column width for larger boxes
        row_height = 200  # Increase row height for taller boxes
        start_x = 200  # Move start position to accommodate larger boxes
        start_y = 120
        
        for i, person_id in enumerate(self.people):
            row = i // cols
            col = i % cols
            self.people[person_id].x = start_x + col * col_width
            self.people[person_id].y = start_y + row * row_height
            
        self.redraw_all()
        
    def redraw_all(self):
        # Clear canvas
        self.canvas.delete("all")
        self.person_widgets.clear()
        self.connection_lines.clear()
        # Recreate the grid pattern after clearing
        self.add_grid_pattern()
        zoom = self._last_zoom if hasattr(self, '_last_zoom') else 1.0
        # Redraw connections first
        for id1, person1 in self.people.items():
            for id2, label in person1.connections.items():
                if id1 < id2:  # Avoid duplicates
                    self.draw_connection(id1, id2, label, zoom=zoom)
        # Redraw people
        for person_id in self.people:            self.create_person_widget(person_id, zoom=zoom)

    def save_data(self):
        filename = filedialog.asksaveasfilename(defaultextension=".csv",
                                              filetypes=[("CSV files", "*.csv")])
        if filename:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['ID', 'Name', 'DOB', 'Alias', 'Address', 'Phone', 'X', 'Y'])
                # Save people
                for person_id, person in self.people.items():
                    writer.writerow([person_id, person.name, person.dob, person.alias, 
                                   person.address, person.phone, person.x, person.y])
                writer.writerow(['CONNECTIONS'])
                writer.writerow(['From_ID', 'To_ID', 'Label'])
                # Save connections
                saved = set()
                for id1, person in self.people.items():
                    for id2, label in person.connections.items():
                        key = (min(id1, id2), max(id1, id2))
                        if key not in saved:
                            writer.writerow([id1, id2, label])
                            saved.add(key)
            messagebox.showinfo("Success", "Data saved successfully!")
            
    def load_data(self):
        filename = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if filename:
            self.clear_all()
            with open(filename, 'r') as f:
                reader = csv.reader(f)
                header = next(reader)
                connections_section = False
                for row in reader:
                    if row and row[0] == 'CONNECTIONS':
                        connections_section = True
                        next(reader)  # Skip connection header
                        continue
                    if connections_section:
                        if len(row) >= 3:
                            id1, id2, label = int(row[0]), int(row[1]), row[2]
                            if id1 in self.people and id2 in self.people:
                                self.people[id1].connections[id2] = label
                                self.people[id2].connections[id1] = label
                            else:
                                logger.warning(f"Connection references missing person: {id1} or {id2}")
                    else:
                        if len(row) >= 8:
                            person_id = int(row[0])
                            person = Person(row[1], row[2], row[3], row[4], row[5])
                            person.x = float(row[6])
                            person.y = float(row[7])
                            self.people[person_id] = person
                            self.next_id = max(self.next_id, person_id + 1)
                self.redraw_all()
                messagebox.showinfo("Success", "Data loaded successfully!")
            
    def clear_all(self):
        self.canvas.delete("all")
        self.people.clear()
        self.person_widgets.clear()
        self.connection_lines.clear()
        self.selected_person = None
        self.next_id = 1
        # Recreate the grid pattern after clearing
        self.add_grid_pattern()

    def update_status(self, message):
        """Update the status bar with a message"""
        if hasattr(self, 'status_label'):
            self.status_label.config(text=message)
            # Auto-clear status after 5 seconds if it's a temporary message
            if "🔗" in message or "✅" in message or "cancelled" in message:
                self.root.after(5000, lambda: self.update_status("Ready - Right-click a person to start linking"))
    
    def apply_hover_to_person(self, person_id):
        """Apply subtle hover effect to a person that preserves text readability"""
        if person_id in self.person_widgets:
            group = self.person_widgets[person_id]
            for item in group:
                if 'shadow' not in self.canvas.gettags(item) and 'corner' not in self.canvas.gettags(item):
                    try:
                        # Only highlight borders, not backgrounds
                        if self.canvas.type(item) == 'rectangle':
                            self.canvas.itemconfig(item, outline=COLORS['primary'], width=2)
                    except:
                        pass
    
    def remove_hover_from_person(self, person_id):
        """Remove hover effect from a person"""
        if person_id in self.person_widgets:
            group = self.person_widgets[person_id]
            for item in group:
                if 'shadow' not in self.canvas.gettags(item) and 'corner' not in self.canvas.gettags(item):
                    try:
                        if self.canvas.type(item) == 'rectangle':
                            self.canvas.itemconfig(item, outline=COLORS['border'], width=1)
                    except:
                        pass
    
    def on_escape_key(self, event):
        """Handle escape key to cancel connections"""
        if self.connecting:
            self.cancel_connection()
            self.update_status("Connection cancelled with Escape key")
    
    def on_delete_key(self, event):
        """Handle delete key to remove selected connection"""
        if self.selected_connection:
            self.delete_connection()
    
    def clear_connection_selection(self):
        """Clear the current connection selection"""
        if self.selected_connection:
            self.unhighlight_connection_selection()
            self.selected_connection = None
    
    def highlight_connection_selection(self):
        """Highlight the selected connection"""
        if self.selected_connection and self.selected_connection in self.connection_lines:
            elements = self.connection_lines[self.selected_connection]
            if len(elements) >= 7:
                _, _, _, label_bg, _, _, _ = elements
                # Highlight the label background
                self.canvas.itemconfig(label_bg, outline=COLORS['primary'], width=3)
    
    def unhighlight_connection_selection(self):
        """Remove highlight from the selected connection"""
        if self.selected_connection and self.selected_connection in self.connection_lines:
            elements = self.connection_lines[self.selected_connection]
            if len(elements) >= 7:
                _, _, _, label_bg, _, _, _ = elements
                # Restore normal appearance
                self.canvas.itemconfig(label_bg, outline=COLORS['secondary'], width=2)
    
    def delete_connection(self):
        """Delete the selected connection"""
        if not self.selected_connection:
            return
            
        id1, id2 = self.selected_connection
        
        # Remove from canvas
        if self.selected_connection in self.connection_lines:
            elements = self.connection_lines[self.selected_connection] 
            for element in elements:
                self.canvas.delete(element)
            del self.connection_lines[self.selected_connection]
        
        # Remove from data structure
        if id1 in self.people and id2 in self.people[id1].connections:
            del self.people[id1].connections[id2]
        if id2 in self.people and id1 in self.people[id2].connections:
            del self.people[id2].connections[id1]
        
        self.selected_connection = None
        self.update_status("Connection deleted")
        
    def edit_connection_label(self):
        """Edit the label of the selected connection"""
        if not self.selected_connection:
            return
        id1, id2 = self.selected_connection
        # Get current label
        current_label = self.people[id1].connections.get(id2, "")
        dialog = ConnectionLabelDialog(self.root, "Edit Connection Label", current_label=current_label)
        dialog.dialog.wait_window()
        if dialog.result is not None:
            # Update label in data structure
            self.people[id1].connections[id2] = dialog.result
            self.people[id2].connections[id1] = dialog.result
            # Update the label text on the canvas immediately
            key = (min(id1, id2), max(id1, id2))
            elements = self.connection_lines.get(key)
            if elements and len(elements) >= 7:
                label_text = elements[5]
                self.canvas.itemconfig(label_text, text=dialog.result)
            # Redraw the connection (for size/position)
            self.update_connections()
            self.update_status(f"✏️ Connection label updated: {dialog.result}")
    
    def normalize_all_widgets_to_current_zoom(self):
        """Ensure all person widgets are at the correct zoom level for consistent interaction"""
        if not hasattr(self, '_last_zoom'):
            return
            
        # Recreate all person widgets at the current zoom level
        for person_id in list(self.people.keys()):
            self.refresh_person_widget(person_id)
        
        # Recreate all connections at the current zoom level
        self.update_connections()
        
        # Redraw grid at current zoom
        self.redraw_grid()

    # --- Zoom and Pan Handlers ---
    
    def on_canvas_zoom(self, event):
        # Zoom in/out with scroll wheel, centered on mouse pointer
        scale = 1.1 if event.delta > 0 else 0.9
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self.canvas.scale("all", x, y, scale, scale)
        
        # Update the _last_zoom variable to maintain consistency with the slider
        if hasattr(self, '_last_zoom'):
            self._last_zoom *= scale
        else:
            self._last_zoom = scale
              # Update the zoom slider to reflect the new zoom level
        self.zoom_var.set(self._last_zoom)
        
        # Update scroll region to accommodate new zoom level
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_middle_button_press(self, event):
        logger.info(f"Middle mouse button pressed at ({event.x}, {event.y})")
        self.canvas.scan_mark(event.x, event.y)
        self._panning = True

    def on_middle_button_motion(self, event):
        if hasattr(self, '_panning') and self._panning:
            logger.info(f"Middle mouse button drag to ({event.x}, {event.y})")
            # Use gain=1 since we're not dealing with zoom scaling issues anymore
            # The zoom scaling is applied to the canvas items, not the scroll region
            self.canvas.scan_dragto(event.x, event.y, gain=1)

    def on_middle_button_release(self, event):
        logger.info(f"Middle mouse button released at ({event.x}, {event.y})")
        self._panning = False

if __name__ == "__main__":
    logger.info("Starting application")
    root = tk.Tk()
    logger.info("Tkinter root created")
    app = ConnectionApp(root)
    logger.info("Starting main loop")
    root.mainloop()
    logger.info("Application ended")