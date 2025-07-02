import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import csv
import math
from datetime import datetime
import os
from collections import defaultdict
import logging
from logging.handlers import TimedRotatingFileHandler
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
from src.models import Person
from src.dialogs import PersonDialog, ConnectionLabelDialog, VersionUpdateDialog, NoUpdateDialog

# Set up logging with both console and daily rotating file
def setup_logging():
    # Create logs directory in AppData/Local/COMRADE
    appdata_local = os.environ.get('LOCALAPPDATA', os.path.expanduser('~\\AppData\\Local'))
    log_dir = os.path.join(appdata_local, 'COMRADE')
    os.makedirs(log_dir, exist_ok=True)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with daily rotation using COMRADE-YYYY-MM-DD.log format
    today = datetime.now().strftime('%Y-%m-%d')
    log_filename = os.path.join(log_dir, f'COMRADE-{today}.log')
    file_handler = TimedRotatingFileHandler(
        log_filename,
        when='midnight',
        interval=1,
        backupCount=30,  # Keep 30 days of logs
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    # Custom namer function to create COMRADE-YYYY-MM-DD.log format
    def custom_namer(default_name):
        # Extract the date from the default name and format it properly
        base_dir = os.path.dirname(default_name)
        # The default name will be something like COMRADE-2025-07-02.log.2025-07-03
        # We want to extract the date and create COMRADE-YYYY-MM-DD.log
        parts = os.path.basename(default_name).split('.')
        if len(parts) >= 2:
            date_part = parts[-1]  # Get the date suffix
            return os.path.join(base_dir, f'COMRADE-{date_part}.log')
        return default_name
    
    file_handler.namer = custom_namer
    root_logger.addHandler(file_handler)

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

COMRADE_VERSION = "0.6.5"



class ConnectionApp:
    def __init__(self, root):
        logger.info("Initializing ConnectionApp")
        self.root = root
        self.root.title("COMRADE")
        self.root.geometry("1400x900")
        self.root.configure(bg=COLORS['background'])
        
        # Configure modern styling
        self.setup_styles()        # Data structures
        self.people = {}  # {id: Person}
        self.person_widgets = {}  # {id: canvas_item_id}
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
        self.selected_connection = None  # Track selected connection for editing/deletion
        self.dragging = False
        self.drag_data = {"x": 0, "y": 0}
        self.connecting = False
        self.connection_start = None
        self.temp_line = None
        self.next_id = 1
        
        logger.info("Setting up UI")
        self.setup_ui()
        
        # Clean up old extracted files on startup
        self.cleanup_old_files()
        
        # Check for updates automatically on startup (with a delay to let UI load)
        self.root.after(2000, self.check_for_updates_silently)  # 2 second delay
        
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
        self.create_modern_button(toolbar, "❌ Delete Person", self.delete_person, COLORS['danger'])
        self.create_modern_button(toolbar, "💾 Save Project", self.save_data, COLORS['accent'])
        self.create_modern_button(toolbar, "📁 Load Project", self.load_data, COLORS['accent'])
        self.create_modern_button(toolbar, "🖼️ Export PNG", self.export_to_png, COLORS['secondary'])
        self.create_modern_button(toolbar, "🔄 Check Updates", self.check_for_updates, COLORS['accent'])
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
        
        # Initialize fixed scroll region for consistent canvas size
        self.fixed_canvas_width = 2800  # 2x the default width for more space
        self.fixed_canvas_height = 1800  # 2x the default height for more space
          # Add subtle grid pattern to canvas
        self.add_grid_pattern()
        
        # Bind events
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-2>", self.on_middle_button_press)
        self.canvas.bind("<B2-Motion>", self.on_middle_button_motion)
        self.canvas.bind("<ButtonRelease-2>", self.on_middle_button_release)
        # Bind mouse wheel for zoom control
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        # Make canvas focusable and bind keys
        self.canvas.configure(highlightthickness=1, highlightcolor=COLORS['primary'])
        self.canvas.bind("<Key-Escape>", self.on_escape_key)
        self.canvas.bind("<Key-Delete>", self.on_delete_key)
        self.canvas.bind("<Key-BackSpace>", self.on_delete_key)  # Also bind backspace
        self.canvas.bind("<Key-c>", self.on_color_cycle_key)  # Color cycling
        self.root.bind("<Key-Escape>", self.on_escape_key)  # Also bind to root for global access
        self.root.bind("<Key-Delete>", self.on_delete_key)
        self.root.bind("<Key-BackSpace>", self.on_delete_key)
        self.root.bind("<Key-c>", self.on_color_cycle_key)
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
        self.status_label.pack(side=tk.LEFT)        # --- Zoom slider ---
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
        
        # Set the initial scroll region
        self.canvas.configure(scrollregion=(0, 0, self.fixed_canvas_width, self.fixed_canvas_height))
    
    def on_zoom(self, value):
        # Scale the canvas content based on the zoom value
        try:
            zoom = float(value)
        except ValueError:
            zoom = 1.0
        
        # Avoid unnecessary work if zoom hasn't changed significantly
        if hasattr(self, '_last_zoom') and abs(zoom - self._last_zoom) < 0.01:
            return
        
        # Store previous zoom for efficient scaling
        prev_zoom = self._last_zoom if hasattr(self, '_last_zoom') else 1.0
        
        # Use single canvas.scale operation for better performance
        scale_factor = zoom / prev_zoom
        self.canvas.scale("all", 0, 0, scale_factor, scale_factor)
        self._last_zoom = zoom
        
        # Keep the scroll region fixed to maintain consistent canvas size
        self.canvas.configure(scrollregion=(0, 0, self.fixed_canvas_width, self.fixed_canvas_height))
        
        # Batch UI updates for better performance
        self.debounced_zoom_update(zoom)

    def debounced_zoom_update(self, zoom):
        """Perform expensive zoom operations with debouncing"""
        # Cancel previous timer if it exists
        if self.zoom_debounce_timer:
            self.root.after_cancel(self.zoom_debounce_timer)
        
        # Schedule the expensive operations after a short delay
        self.zoom_debounce_timer = self.root.after(50, lambda: self._perform_zoom_update(zoom))
    
    def _perform_zoom_update(self, zoom):
        """Perform the actual expensive zoom update operations"""
        self.rescale_text(zoom)
        self.rescale_images_optimized(zoom)
        self.redraw_grid()
        self.zoom_debounce_timer = None

    def rescale_images(self, zoom):
        """Rescale all image items on the canvas based on their original dimensions"""
        if not hasattr(self, 'image_refs'):
            return
        
        # Collect image items first to avoid repeated canvas.find_all() calls
        image_items = []
        for item in self.canvas.find_all():
            if self.canvas.type(item) == 'image' and 'image' in self.canvas.gettags(item):
                image_items.append(item)
        
        # Process image items in batch
        for item in image_items:
            # Scale from the original image size if we have it stored
            if item in self.original_image_sizes and item in self.image_refs:
                original_width, original_height = self.original_image_sizes[item]
                new_width = max(10, int(original_width * zoom))
                new_height = max(10, int(original_height * zoom))
                
                # Get the person_id from the canvas item tags to find the image file
                tags = self.canvas.gettags(item)
                person_tag = None
                for tag in tags:
                    if tag.startswith('person_'):
                        person_tag = tag
                        break
                
                if person_tag:
                    person_id = int(person_tag.split('_')[1])
                    if person_id in self.people:
                        person = self.people[person_id]
                        
                        # Find the image file for this person
                        image_file = None
                        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
                        if hasattr(person, 'files') and person.files:
                            for file_path in person.files:
                                if os.path.exists(file_path) and os.path.splitext(file_path.lower())[1] in image_extensions:
                                    image_file = file_path
                                    break
                        
                        if image_file and PIL_AVAILABLE:
                            try:
                                # Check cache first
                                cache_key = (image_file, new_width, new_height)
                                if cache_key in self.image_cache:
                                    # Use cached image
                                    new_photo = self.image_cache[cache_key]
                                else:
                                    # Load and resize image, then cache it
                                    pil_image = Image.open(image_file)
                                    pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                                    
                                    # Convert to PhotoImage
                                    from PIL import ImageTk
                                    new_photo = ImageTk.PhotoImage(pil_image)
                                    
                                    # Cache the resized image
                                    self.image_cache[cache_key] = new_photo
                                    
                                    # Manage cache size to prevent memory issues
                                    if len(self.image_cache) > 50:  # Limit cache size
                                        # Remove oldest entries
                                        keys_to_remove = list(self.image_cache.keys())[:-40]  # Keep last 40
                                        for old_key in keys_to_remove:
                                            del self.image_cache[old_key]
                                
                                # Update the canvas image
                                self.canvas.itemconfig(item, image=new_photo)
                                
                                # Update the reference to prevent garbage collection
                                self.image_refs[item] = new_photo
                                
                            except Exception as e:
                                logger.warning(f"Failed to rescale image for person {person_id}: {e}")

    def rescale_text(self, zoom):
        # Rescale all text items on the canvas based on their original font sizes
        text_items = []
        for item in self.canvas.find_all():
            if self.canvas.type(item) == 'text':
                text_items.append(item)
        
        # Process text items in batch
        for item in text_items:
            # If we don't have the original font size stored, store it now
            if item not in self.original_font_sizes:
                current_font = self.canvas.itemcget(item, 'font')
                # Parse font string: e.g., 'Segoe UI 10 bold'
                parts = current_font.split()
                # Find the first integer in the font string (the size)
                base_size = 10  # default fallback
                for part in parts:
                    if part.isdigit():
                        base_size = int(part)
                        break
                self.original_font_sizes[item] = base_size
            
            # Scale from the original font size
            original_size = self.original_font_sizes[item]
            new_size = max(6, int(original_size * zoom))
            
            # Get current font to preserve style
            current_font = self.canvas.itemcget(item, 'font')
            parts = current_font.split()
            
            # Rebuild font string with new size
            if len(parts) >= 2:
                # Replace the size part
                for i, part in enumerate(parts):
                    if part.isdigit():
                        parts[i] = str(new_size)
                        break
                new_font = ' '.join(parts)
            else:
                # Fallback format
                new_font = f"Segoe UI {new_size}"
            
            self.canvas.itemconfig(item, font=new_font)

    def on_canvas_resize(self, event):
        self.redraw_grid()

    def redraw_grid(self):
        # Remove old grid
        self.canvas.delete("grid")
        # Use fixed canvas dimensions instead of current widget size
        width = self.fixed_canvas_width
        height = self.fixed_canvas_height
        grid_size = 40 * (self._last_zoom if hasattr(self, '_last_zoom') else 1)
        
        # Optimize by creating fewer grid lines when zoomed out
        min_grid_spacing = 20  # Minimum spacing between grid lines in pixels
        if grid_size < min_grid_spacing:
            grid_size = min_grid_spacing
        
        # Create vertical lines with step optimization
        x_step = max(int(grid_size), 40)
        for x in range(0, int(width + x_step), x_step):
            self.canvas.create_line(x, 0, x, height, fill='#e2e8f0', width=1, tags="grid")
        
        # Create horizontal lines with step optimization  
        y_step = max(int(grid_size), 40)
        for y in range(0, int(height + y_step), y_step):
            self.canvas.create_line(0, y, width, y, fill='#e2e8f0', width=1, tags="grid")
        
        # Always send grid to the very back, behind all other elements
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
        # Use the fixed canvas size for consistent grid coverage
        canvas_width = self.fixed_canvas_width
        canvas_height = self.fixed_canvas_height
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
        instructions_frame.pack(fill=tk.X, pady=(10, 0))        # Instructions with modern styling
        instructions = [
            "🖱️ Left-click to select and move people",
            "🔗 Right-click to link: first person, then target", 
            "✏️ Double-click on a person to edit their information",
            "⌨️ Press 'C' to cycle selected person's color",
            "❌ Press Delete to remove selected person or connection",
            "🚫 Press Escape to cancel an active connection"
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
            # Extract files separately since Person.__init__ doesn't accept it
            files = dialog.result.pop('files', [])
            person = Person(**dialog.result)
            person.files = files  # Set files after creation
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
            
    def delete_person(self):
        """Delete the currently selected person"""
        if self.selected_person is None:
            messagebox.showwarning("No Selection", "Please select a person to delete by clicking on them first.")
            return
            
        person_id = self.selected_person
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
        self.selected_person = None
        
        logger.info(f"Successfully deleted person {person_id}")
        self.update_status(f"🗑️ Deleted '{person.name}' and their connections")
        
        # Update canvas
        self.canvas.update()
            
    def create_person_widget(self, person_id, zoom=None):
        # Safety check to prevent widget creation during drag operations
        if self.dragging:
            logger.warning(f"Attempted to create widget for person {person_id} during drag - skipping")
            return
            
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
        
        # Check for image files
        image_file = None
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        if hasattr(person, 'files') and person.files:
            for file_path in person.files:
                if os.path.exists(file_path) and os.path.splitext(file_path.lower())[1] in image_extensions:
                    image_file = file_path
                    break
        
        # Calculate modern card dimensions with image consideration
        base_width = max(max(len(line) for line in info_lines) * 9, 200)
        image_width = 120 if image_file else 0  # Reserve space for image
        card_width = (base_width + image_width + (20 if image_file else 0)) * zoom  # Add padding between text and image
        card_height = max(len(info_lines) * 25 + 40, 120, 140 if image_file else 120) * zoom  # Ensure minimum height for image
        
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
          # Get person's color
        person_color = CARD_COLORS[person.color % len(CARD_COLORS)]
        
        # Main card background with gradient effect
        main_card = self.canvas.create_rectangle(
            x - half_width, y - half_height,
            x + half_width, y + half_height,
            fill=COLORS['surface'], 
            outline=person_color, 
            width=2,
            tags=(f"person_{person_id}", "person")
        )
        group.append(main_card)
        
        # Header section with accent color
        header_height = int(30 * zoom)
        header = self.canvas.create_rectangle(
            x - half_width, y - half_height,
            x + half_width, y - half_height + header_height,
            fill=person_color, outline='', width=0,
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
            fill='white', outline=person_color, width=2,
            tags=(f"person_{person_id}", "person")
        )
        group.append(avatar_bg)
          # Avatar icon
        avatar_icon = self.canvas.create_text(
            avatar_x, avatar_y, text="👤",
            font=("Arial", int(10 * zoom)), fill=person_color,
            tags=(f"person_{person_id}", "person")
        )
        self.store_text_font_size(avatar_icon, ("Arial", 10))  # Store original size
        group.append(avatar_icon)
          # Name in header (white text)
        name_text = self.canvas.create_text(
            avatar_x + avatar_size + int(10 * zoom), avatar_y,
            text=person.name or "Unnamed",
            anchor="w", font=("Segoe UI", int(11 * zoom), "bold"), 
            fill='white',
            tags=(f"person_{person_id}", "person")
        )
        self.store_text_font_size(name_text, ("Segoe UI", 11, "bold"))  # Store original size
        group.append(name_text)
        # File indicator if files are attached
        if getattr(person, 'files', []):
            file_icon = self.canvas.create_text(
                avatar_x + avatar_size + int(10 * zoom) + int(8 * zoom) + self.canvas.bbox(name_text)[2] - self.canvas.bbox(name_text)[0],
                avatar_y,
                text="📎",
                anchor="w", font=("Segoe UI Emoji", int(10 * zoom)),
                fill='white',
                tags=(f"person_{person_id}", "person", "file_icon")
            )
            self.store_text_font_size(file_icon, ("Segoe UI Emoji", 10))
            group.append(file_icon)
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
                self.store_text_font_size(icon_item, ("Segoe UI Emoji", 9))  # Store original size
                text_item = self.canvas.create_text(
                    text_x, current_y,
                    text=value,
                    anchor="nw", font=("Segoe UI", int(9 * zoom)),
                    fill=COLORS['text_primary'],
                    tags=(f"person_{person_id}", "person")
                )
                self.store_text_font_size(text_item, ("Segoe UI", 9))  # Store original size
                group.extend([icon_item, text_item])
                current_y += line_height
        
        # Display image if available
        if image_file and PIL_AVAILABLE:
            try:
                # Load and resize image
                pil_image = Image.open(image_file)
                
                # Calculate image dimensions (maintain aspect ratio) - use base size regardless of zoom
                base_max_width = 100  # Base size at zoom=1.0
                base_max_height = 100  # Base size at zoom=1.0 - keep it simple and square
                
                # Calculate scaling to fit within bounds
                img_ratio = pil_image.width / pil_image.height
                if base_max_width / base_max_height > img_ratio:
                    # Height is the limiting factor
                    base_img_height = base_max_height
                    base_img_width = int(base_img_height * img_ratio)
                else:
                    # Width is the limiting factor
                    base_img_width = base_max_width
                    base_img_height = int(base_img_width / img_ratio)
                
                # Apply zoom to get actual display size
                img_width = int(base_img_width * zoom)
                img_height = int(base_img_height * zoom)
                
                # Use optimized caching system
                photo = self.get_scaled_image(image_file, img_width, img_height)
                
                if photo:
                    # Position image on the right side of the card
                    img_x = x + half_width - img_width//2 - int(10 * zoom)  # Right side with padding
                    img_y = y - half_height + header_height + img_height//2 + int(10 * zoom)  # Below header with padding
                    
                    # Create image on canvas
                    img_item = self.canvas.create_image(
                        img_x, img_y,
                        image=photo,
                        anchor="center",
                        tags=(f"person_{person_id}", "person", "image")
                    )
                    
                    # Store reference to prevent garbage collection
                    if not hasattr(self, 'image_refs'):
                        self.image_refs = {}
                    self.image_refs[img_item] = photo
                    
                    # Store image path for efficient re-scaling
                    if not hasattr(photo, 'image_path'):
                        photo.image_path = image_file
                    
                    # Store original (base) image dimensions for proper scaling
                    self.original_image_sizes[img_item] = (base_img_width, base_img_height)
                    
                    group.append(img_item)
                
            except Exception as e:
                logger.error(f"Failed to load image {image_file}: {e}")
        
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
        # Increase tolerance at zoom levels close to 1.0 where precision issues can occur
        base_tolerance = 3
        if 0.9 <= zoom <= 1.1:
            tolerance = int(base_tolerance * 1.5)  # Increase tolerance near zoom 1.0
        else:
            tolerance = base_tolerance
        
        # Convert screen coordinates to canvas coordinates to handle scrolled content
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        # Use canvas coordinates for hit detection
        items = self.canvas.find_overlapping(canvas_x - tolerance, canvas_y - tolerance, canvas_x + tolerance, canvas_y + tolerance)
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
            self.selected_person = selected_person_id
            self.drag_data = {"x": canvas_x, "y": canvas_y}
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
            
            # Convert screen coordinates to canvas coordinates
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            
            # Calculate the movement delta in canvas coordinates
            dx_canvas = canvas_x - self.drag_data["x"]
            dy_canvas = canvas_y - self.drag_data["y"]
            
            # Convert canvas delta to world delta (compensate for zoom)
            dx_world = dx_canvas / zoom
            dy_world = dy_canvas / zoom
            
            logger.debug(f"[DRAG] Zoom: {zoom:.3f}, Canvas: ({canvas_x}, {canvas_y}), "
                         f"Canvas Δ: ({dx_canvas}, {dy_canvas}), World Δ: ({dx_world:.2f}, {dy_world:.2f})")

            # Update logical (unscaled) position using world delta
            self.people[self.selected_person].x += dx_world
            self.people[self.selected_person].y += dy_world
            logger.debug(f"[DRAG] Updated logical position: ({self.people[self.selected_person].x}, {self.people[self.selected_person].y})")

            # Move existing canvas items directly during drag (much more efficient)
            person_items = self.person_widgets[self.selected_person]
            for item in person_items:
                self.canvas.move(item, dx_canvas, dy_canvas)

            # Update connections immediately (but efficiently)
            self.update_connections()            # Update drag data for next movement
            self.drag_data = {"x": canvas_x, "y": canvas_y}

    def on_canvas_release(self, event):
        if self.dragging and self.selected_person:
            # Mark dragging as false first to allow widget refresh
            self.dragging = False
            
            # Handle any pending color refresh from color cycling during drag
            refresh_person = self.selected_person
            if hasattr(self, '_pending_color_refresh') and self._pending_color_refresh:
                refresh_person = self._pending_color_refresh
                delattr(self, '_pending_color_refresh')
            
            # After dragging is complete, refresh the widget to ensure correct positioning
            # This normalizes the widget to the correct zoom level
            # Use a small delay to ensure all drag events are processed
            self.root.after(50, lambda: self.refresh_person_widget(refresh_person) if refresh_person else None)
        else:
            self.dragging = False
    
    def on_double_click(self, event):
        """Handle double-click events for editing connections"""
        # Convert screen coordinates to canvas coordinates
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        items = self.canvas.find_closest(canvas_x, canvas_y)
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
        # Skip mouse move processing during drag operations to prevent interference
        if self.dragging:
            return
             
        # Throttle mouse move events to improve performance
        current_time = datetime.now().timestamp()
        if hasattr(self, '_last_mouse_move_time'):
            if current_time - self._last_mouse_move_time < 0.02:  # 50 FPS max
                return
        self._last_mouse_move_time = current_time
        
        # Update hover effects using more forgiving detection
        # Use a small area around the cursor instead of just the closest point
        tolerance = 5  # pixels
        
        # Convert screen coordinates to canvas coordinates
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        items = self.canvas.find_overlapping(canvas_x - tolerance, canvas_y - tolerance, 
                                           canvas_x + tolerance, canvas_y + tolerance)
        
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
                # Simple hover effect - just change cursor
                if hasattr(self, 'current_hover') and self.current_hover != person_id:
                    # Remove previous hover
                    pass
                if not hasattr(self, 'current_hover') or self.current_hover != person_id:
                    # Apply new hover - just set cursor
                    self.canvas.configure(cursor="hand2")
                    self.current_hover = person_id
        else:
            if hasattr(self, 'current_hover'):
                # Remove hover effect - reset cursor
                self.canvas.configure(cursor="")
                delattr(self, 'current_hover')
        
        # Update temp line if connecting - make it more responsive
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
        
        # Convert screen coordinates to canvas coordinates
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        items = self.canvas.find_overlapping(canvas_x - tolerance, canvas_y - tolerance, 
                                           canvas_x + tolerance, canvas_y + tolerance)
        logger.debug(f"Right-click at canvas ({canvas_x}, {canvas_y}), found items: {items}")
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
            self.start_connection(person_id, canvas_x, canvas_y)
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
        # x and y are already canvas coordinates from the caller
        self.temp_line = self.canvas.create_line(start_x, start_y, x, y, 
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
        
        label_text = self.canvas.create_text(
            mid_x, mid_y,
            text=label,
            font=("Segoe UI", int(10 * zoom)),
            tags=("connection", f"connection_label_{min(id1, id2)}_{max(id1, id2)}"))
        self.store_text_font_size(label_text, ("Segoe UI", 10))  # Store original size
        
        # Make label clickable by adding larger invisible area
        clickable_area = self.canvas.create_rectangle(
            mid_x - half_width, mid_y - half_height, 
            mid_x + half_width, mid_y + half_height,
            fill="", outline="", width=0,
            tags=("connection", f"connection_clickable_{min(id1, id2)}_{max(id1, id2)}"))
        
        # Store connection info with all elements
        key = (min(id1, id2), max(id1, id2))
        self.connection_lines[key] = (shadow_line, line, label_shadow, label_bg, label_text, clickable_area)
          # Move connections to back but labels to front
        self.canvas.tag_lower(shadow_line)
        self.canvas.tag_lower(line)
        self.canvas.tag_raise(label_shadow)
        self.canvas.tag_raise(label_bg)
        self.canvas.tag_raise(label_text)
        
        # Ensure grid stays behind all elements
        self.canvas.tag_lower("grid")
        
    def update_connections(self):
        zoom = self._last_zoom if hasattr(self, '_last_zoom') else 1.0
        # Redraw all modern connections
        for (id1, id2), elements in self.connection_lines.items():
            if len(elements) >= 6:  # New format with 6 elements (removed icon)
                shadow_line, line, label_shadow, label_bg, label_text, clickable_area = elements

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
                self.canvas.coords(label_text, mid_x, mid_y)          # Ensure grid stays behind all elements after updating connections
        self.canvas.tag_lower("grid")
    
    def edit_person(self, person_id):
        person = self.people[person_id]
        dialog = PersonDialog(self.root, "Edit Person", 
                            name=person.name, dob=person.dob, 
                            alias=person.alias, address=person.address,                            phone=person.phone, files=person.files)
        self.root.wait_window(dialog.dialog)  # Wait for dialog to close
        if dialog.result:
            # Update person data
            for key, value in dialog.result.items():
                setattr(person, key, value)
            # Update display
            self.refresh_person_widget(person_id)
    
    def refresh_person_widget(self, person_id):
        # Prevent widget refresh during drag operations to avoid freezing
        if self.dragging:
            return
        
        # Delete old widget and clean up font size tracking
        for item in self.person_widgets[person_id]:
            self.canvas.delete(item)
            # Clean up font size tracking for text items
            if item in self.original_font_sizes:
                del self.original_font_sizes[item]
            # Clean up image size tracking for image items
            if item in self.original_image_sizes:
                del self.original_image_sizes[item]
            # Clean up image references
            if hasattr(self, 'image_refs') and item in self.image_refs:
                del self.image_refs[item]
        # Create new widget
        self.create_person_widget(person_id)
        # Restore connections to back
        self.canvas.tag_lower("connection")
        # Ensure grid stays behind all elements
        self.canvas.tag_lower("grid")
        
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
        # Clear tracking data
        self.original_font_sizes.clear()
        self.original_image_sizes.clear()
        if hasattr(self, 'image_refs'):
            self.image_refs.clear()
        # Clear image cache to free memory
        if hasattr(self, 'image_cache'):
            self.image_cache.clear()
        # Recreate the grid pattern after clearing
        self.add_grid_pattern()
        zoom = self._last_zoom if hasattr(self, '_last_zoom') else 1.0
        # Redraw connections first
        for id1, person1 in self.people.items():
            for id2, label in person1.connections.items():
                if id1 < id2:  # Avoid duplicates
                    self.draw_connection(id1, id2, label, zoom=zoom)        # Redraw people
        for person_id in self.people:
            self.create_person_widget(person_id, zoom=zoom)
          # Ensure proper layering: grid at bottom, connections in middle, people on top
        self.canvas.tag_lower("grid")

    def save_data(self):
        """Save data as a ZIP file containing CSV and all attached files"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("COMRADE files", "*.zip"), ("All files", "*.*")]
        )
        if not filename:
            return
            
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create CSV file in temp directory
                csv_path = os.path.join(temp_dir, "data.csv")
                file_mapping = {}  # Maps original paths to ZIP internal paths
                
                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['ID', 'Name', 'DOB', 'Alias', 'Address', 'Phone', 'X', 'Y', 'Color', 'Files'])
                    
                    # Save people
                    for person_id, person in self.people.items():
                        # Process attached files
                        zip_file_paths = []
                        if hasattr(person, 'files') and person.files:
                            for file_path in person.files:
                                if os.path.exists(file_path):
                                    # Create unique filename in ZIP
                                    filename_only = os.path.basename(file_path)
                                    name, ext = os.path.splitext(filename_only)
                                    zip_internal_path = f"files/{person_id}_{name}{ext}"
                                    
                                    # Handle duplicate filenames
                                    counter = 1
                                    while zip_internal_path in file_mapping.values():
                                        zip_internal_path = f"files/{person_id}_{name}_{counter}{ext}"
                                        counter += 1
                                    
                                    file_mapping[file_path] = zip_internal_path
                                    zip_file_paths.append(zip_internal_path)
                        
                        # Convert file paths list to JSON string for CSV storage
                        files_json = json.dumps(zip_file_paths) if zip_file_paths else ""
                        
                        writer.writerow([
                            person_id, person.name, person.dob, person.alias, 
                            person.address, person.phone, person.x, person.y, 
                            person.color, files_json
                        ])
                    
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
                
                # Create ZIP file
                with zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    # Add CSV file
                    zipf.write(csv_path, "data.csv")
                    
                    # Add all attached files
                    for original_path, zip_path in file_mapping.items():
                        if os.path.exists(original_path):
                            zipf.write(original_path, zip_path)
                        else:
                            logger.warning(f"File not found: {original_path}")
            
            messagebox.showinfo("Success", f"Data saved successfully to {os.path.basename(filename)}!\n\nContains:\n• Network data (CSV)\n• {len(file_mapping)} attached files")
            
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            messagebox.showerror("Error", f"Failed to save data: {str(e)}")
            
    def load_data(self):
        """Load data from a ZIP file containing CSV and attached files"""
        filename = filedialog.askopenfilename(
            filetypes=[("COMRADE files", "*.zip"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not filename:
            return
            
        try:
            # Handle both ZIP and legacy CSV files
            if filename.lower().endswith('.zip'):
                self._load_from_zip(filename)
            else:
                self._load_legacy_csv(filename)
                
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            messagebox.showerror("Error", f"Failed to load data: {str(e)}")
    
    def _load_from_zip(self, zip_filename):
        """Load data from ZIP file format"""
        self.clear_all()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(zip_filename, 'r') as zipf:
                # Extract all files to temp directory
                zipf.extractall(temp_dir)
                
                # Read CSV data
                csv_path = os.path.join(temp_dir, "data.csv")
                if not os.path.exists(csv_path):
                    raise ValueError("Invalid COMRADE file: data.csv not found")
                
                # Create a permanent directory for extracted files
                app_data_dir = os.path.expanduser("~/.comrade_files")
                if not os.path.exists(app_data_dir):
                    os.makedirs(app_data_dir)
                
                # Create unique subdirectory for this load
                import time
                load_id = str(int(time.time()))
                files_dir = os.path.join(app_data_dir, f"load_{load_id}")
                os.makedirs(files_dir, exist_ok=True)
                
                with open(csv_path, 'r', encoding='utf-8') as f:
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
                                
                                # Handle color field
                                if len(row) >= 9:
                                    person.color = int(row[8])
                                else:
                                    person.color = 0
                                
                                # Handle files field (new format)
                                if len(row) >= 10 and row[9]:
                                    try:
                                        zip_file_paths = json.loads(row[9])
                                        person.files = []
                                        
                                        # Copy files from temp to permanent location and update paths
                                        for zip_path in zip_file_paths:
                                            temp_file_path = os.path.join(temp_dir, zip_path)
                                            if os.path.exists(temp_file_path):
                                                # Create permanent file path
                                                filename_only = os.path.basename(zip_path)
                                                permanent_path = os.path.join(files_dir, filename_only)
                                                
                                                # Copy file to permanent location
                                                shutil.copy2(temp_file_path, permanent_path)
                                                person.files.append(permanent_path)
                                            else:
                                                logger.warning(f"Attached file not found in ZIP: {zip_path}")
                                    except json.JSONDecodeError:
                                        logger.warning(f"Invalid files data for person {person_id}")
                                        person.files = []
                                else:
                                    person.files = []
                                
                                self.people[person_id] = person
                                self.next_id = max(self.next_id, person_id + 1)
                
                self.redraw_all()
                
                # Count extracted files
                total_files = sum(len(person.files) for person in self.people.values())
                messagebox.showinfo("Success", f"Data loaded successfully!\n\nLoaded:\n• {len(self.people)} people\n• {total_files} attached files\n\nFiles extracted to: {files_dir}")
    
    def _load_legacy_csv(self, csv_filename):
        """Load data from legacy CSV format (backward compatibility)"""
        self.clear_all()
        
        with open(csv_filename, 'r', encoding='utf-8') as f:
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
                        
                        # Handle color field for backward compatibility
                        if len(row) >= 9:
                            person.color = int(row[8])
                        else:
                            person.color = 0
                            
                        # No files in legacy format
                        person.files = []
                        
                        self.people[person_id] = person
                        self.next_id = max(self.next_id, person_id + 1)
            
            self.redraw_all()
            messagebox.showinfo("Success", "Legacy CSV data loaded successfully!\n\nNote: Use the new ZIP format for file attachments.")
    
    def export_to_png(self):
        """Export the current network diagram to PNG format at high DPI
        
        This function exports the complete network visualization including:
        - All person cards with their information
        - Connection lines and labels
        - Attached images for people (if any)
        - High DPI quality for crisp output
        """
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
            
        try:            # High DPI settings for crisp output
            dpi_scale = 6.0  # 6x scaling for high DPI (600 DPI equivalent)
            target_dpi = 600  # Target DPI for print quality
            
            # Use the fixed canvas dimensions scaled up for high DPI
            base_width = self.fixed_canvas_width
            base_height = self.fixed_canvas_height
            canvas_width = int(base_width * dpi_scale)
            canvas_height = int(base_height * dpi_scale)
            
            # Create a white background image at high resolution
            image = Image.new('RGB', (canvas_width, canvas_height), '#f8fafc')
            draw = ImageDraw.Draw(image)
            
            # Get current zoom level and apply DPI scaling
            base_zoom = self._last_zoom if hasattr(self, '_last_zoom') else 1.0
            zoom = base_zoom * dpi_scale
              # Draw grid pattern (scaled for high DPI)
            grid_size = int(40 * dpi_scale)
            grid_color = '#e2e8f0'
            grid_width = max(1, int(1 * dpi_scale))
            for x in range(0, canvas_width, grid_size):
                draw.line([(x, 0), (x, canvas_height)], fill=grid_color, width=grid_width)
            for y in range(0, canvas_height, grid_size):
                draw.line([(0, y), (canvas_width, y)], fill=grid_color, width=grid_width)
            
            # Draw connections first (so they appear behind people)
            for (id1, id2), label in [(ids, self.people[ids[0]].connections.get(ids[1], "")) 
                                    for ids in self.connection_lines.keys()]:
                if id1 in self.people and id2 in self.people:
                    p1, p2 = self.people[id1], self.people[id2]
                    x1, y1 = int(p1.x * zoom), int(p1.y * zoom)
                    x2, y2 = int(p2.x * zoom), int(p2.y * zoom)
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
                x = int(person.x * zoom)
                y = int(person.y * zoom)
                  # Calculate card dimensions
                info_lines = [
                    f"Name: {person.name}" if person.name else "Name: Unnamed",
                    f"DOB: {person.dob}" if person.dob else "",
                    f"Alias: {person.alias}" if person.alias else "",
                    f"Addr: {person.address}" if person.address else "",
                    f"Phone: {person.phone}" if person.phone else ""
                ]
                info_lines = [line for line in info_lines if line.strip()]
                
                # Check for image files (same logic as canvas display)
                image_file = None
                image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
                if hasattr(person, 'files') and person.files:
                    for file_path in person.files:
                        if os.path.exists(file_path) and os.path.splitext(file_path.lower())[1] in image_extensions:
                            image_file = file_path
                            break
                
                # Calculate card dimensions with DPI scaling and image consideration
                base_width = max(max(len(line) for line in info_lines) * 9, 200)
                image_width = 120 if image_file else 0  # Reserve space for image
                card_width = (base_width + image_width + (20 if image_file else 0)) * zoom  # Add padding between text and image
                card_height = max(len(info_lines) * 25 + 40, 120, 140 if image_file else 120) * zoom  # Ensure minimum height for image
                
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
                
                # Get person's color for consistency with canvas display
                person_color = CARD_COLORS[person.color % len(CARD_COLORS)]
                
                # Draw main card with DPI scaling
                card_border_width = max(1, int(2 * dpi_scale))
                draw.rectangle([
                    x - half_width, y - half_height,
                    x + half_width, y + half_height
                ], fill=COLORS['surface'], outline=person_color, width=card_border_width)
                
                # Draw header
                header_height = int(30 * zoom)
                draw.rectangle([
                    x - half_width, y - half_height,
                    x + half_width, y - half_height + header_height
                ], fill=person_color)
                
                # Draw avatar background with DPI scaling
                avatar_size = int(20 * zoom)
                avatar_x = x - half_width + int(15 * zoom)
                avatar_y = y - half_height + int(15 * zoom)
                avatar_border_width = max(1, int(2 * dpi_scale))
                
                draw.ellipse([
                    avatar_x - avatar_size//2, avatar_y - avatar_size//2,
                    avatar_x + avatar_size//2, avatar_y + avatar_size//2
                ], fill='white', outline=person_color, width=avatar_border_width)
                
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
                    ("Phone:", person.phone)                ]
                
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
                
                # Draw attached image if available
                if hasattr(person, 'files') and person.files:
                    image_file = None
                    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
                    for file_path in person.files:
                        if os.path.exists(file_path) and os.path.splitext(file_path.lower())[1] in image_extensions:
                            image_file = file_path
                            break
                    
                    if image_file:
                        try:
                            # Load and resize image for export
                            person_image = Image.open(image_file)
                            
                            # Calculate image dimensions (maintain aspect ratio)
                            base_max_width = int(100 * dpi_scale)  # Scaled for high DPI
                            base_max_height = int(100 * dpi_scale)  # Scaled for high DPI
                            
                            # Calculate scaling to fit within bounds
                            img_ratio = person_image.width / person_image.height
                            if base_max_width / base_max_height > img_ratio:
                                # Height is the limiting factor
                                img_height = base_max_height
                                img_width = int(img_height * img_ratio)
                            else:
                                # Width is the limiting factor
                                img_width = base_max_width
                                img_height = int(img_width / img_ratio)
                            
                            # Resize the image
                            person_image = person_image.resize((img_width, img_height), Image.Resampling.LANCZOS)
                            
                            # Position image on the right side of the card
                            img_x = x + half_width - img_width//2 - int(10 * dpi_scale)  # Right side with padding
                            img_y = y - half_height + header_height + img_height//2 + int(10 * dpi_scale)  # Below header with padding
                            
                            # Paste the image onto the main image
                            image.paste(person_image, (img_x - img_width//2, img_y - img_height//2))
                            
                        except Exception as e:
                            logger.error(f"Failed to include image {image_file} in PNG export: {e}")
            
            # Save the image with high DPI information
            image.save(filename, 'PNG', dpi=(target_dpi, target_dpi))
            messagebox.showinfo("Success", f"High DPI network exported successfully to:\n{filename}\n\nResolution: {canvas_width}x{canvas_height} pixels\nDPI: {target_dpi}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export PNG:\n{str(e)}")
    
    def clear_all(self):
        # Show confirmation dialog
        if not self.people:
            messagebox.showinfo("Nothing to Clear", "There are no people or connections to clear.")
            return
            
        result = messagebox.askyesno(
            "Confirm Clear All", 
            f"Are you sure you want to clear all data?\n\n"
            f"This will permanently delete:\n"
            f"• {len(self.people)} people\n"
            f"• {sum(len(person.connections) for person in self.people.values()) // 2} connections\n\n"
            f"This action cannot be undone!",
            icon='warning'
        )
        
        if not result:
            return
            
        # Proceed with clearing
        self.canvas.delete("all")
        self.people.clear()
        self.person_widgets.clear()
        self.connection_lines.clear()
        self.original_font_sizes.clear()  # Clear font size tracking
        self.selected_person = None
        self.next_id = 1
        # Recreate the grid pattern after clearing
        self.add_grid_pattern()
        
        # Update status
        self.update_status("All data cleared successfully")

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
        """Handle delete key to remove selected connection or person"""
        if self.selected_connection:
            self.delete_connection()
        elif self.selected_person:
            self.delete_person()
    
    def on_color_cycle_key(self, event):
        """Handle 'c' key to cycle colors of selected person"""
        if self.selected_person:
            person = self.people[self.selected_person]
            person.color = (person.color + 1) % len(CARD_COLORS)
            
            # Only refresh widget if not currently dragging
            if not self.dragging:
                self.refresh_person_widget(self.selected_person)
                self.update_status(f"Changed {person.name}'s color to {CARD_COLORS[person.color]}")
            else:
                # Schedule the refresh for after drag operation
                self.update_status(f"Color changed to {CARD_COLORS[person.color]} - will apply after drag")
                self._pending_color_refresh = self.selected_person
    
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
                # Clean up font size tracking for text items
                if element in self.original_font_sizes:
                    del self.original_font_sizes[element]
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
        self.redraw_grid()      # --- Zoom and Pan Handlers ---    
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

    def on_mouse_wheel(self, event):
        """Handle mouse wheel events to change the zoom slider"""
        current_zoom = self.zoom_var.get()
        zoom_step = 0.05
        new_zoom = min(current_zoom + zoom_step, 1.0) if event.delta > 0 else max(current_zoom - zoom_step, 0.5)
        self.zoom_var.set(new_zoom)
        self.on_zoom(new_zoom)

    def store_text_font_size(self, text_item, font_string):
        """Store the original font size for a text item to enable proper scaling"""
        if isinstance(font_string, tuple):
            # Font specified as tuple (family, size, style)
            size = font_string[1] if len(font_string) > 1 else 10
        else:
            # Font specified as string, parse it
            parts = str(font_string).split()
            size = 10  # default
            for part in parts:
                if part.isdigit():
                    size = int(part)
                    break
        self.original_font_sizes[text_item] = size

    def cleanup_old_files(self):
        """Clean up old extracted files to save disk space"""
        try:
            app_data_dir = os.path.expanduser("~/.comrade_files")
            if not os.path.exists(app_data_dir):
                return
            
            import time
            current_time = time.time()
            # Remove directories older than 30 days
            max_age = 30 * 24 * 60 * 60  # 30 days in seconds
            
            for item in os.listdir(app_data_dir):
                item_path = os.path.join(app_data_dir, item)
                if os.path.isdir(item_path) and item.startswith("load_"):
                    try:
                        # Extract timestamp from directory name
                        timestamp = int(item.replace("load_", ""))
                        if current_time - timestamp > max_age:
                            shutil.rmtree(item_path)
                            logger.info(f"Cleaned up old files directory: {item}")
                    except (ValueError, OSError) as e:
                        logger.warning(f"Could not clean up directory {item}: {e}")
                        
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")

    def cleanup_image_cache(self):
        """Clean up image caches to prevent memory bloat"""
        # Clean scaled image cache if it gets too large
        if len(self.scaled_image_cache) > self.max_cache_size * 2:
            # Keep only the most recently used half
            items = list(self.scaled_image_cache.items())
            keep_count = self.max_cache_size
            self.scaled_image_cache = dict(items[-keep_count:])
            logger.info(f"Cleaned scaled image cache, keeping {keep_count} entries")
        
        # Clean base image cache if it gets too large (keep fewer base images)
        if len(self.base_image_cache) > 20:
            items = list(self.base_image_cache.items())
            keep_count = 10
            self.base_image_cache = dict(items[-keep_count:])
            logger.info(f"Cleaned base image cache, keeping {keep_count} entries")

    def clear_image_caches(self):
        """Clear all image caches - useful when loading new data"""
        self.scaled_image_cache.clear()
        self.base_image_cache.clear()
        self.get_base_image.cache_clear()  # Clear LRU cache
        logger.info("Cleared all image caches")
    
    @lru_cache(maxsize=100)
    def get_base_image(self, image_path):
        """Get cached PIL Image for given path"""
        if image_path not in self.base_image_cache:
            try:
                pil_image = Image.open(image_path)
                # Convert to RGB if necessary for consistent handling
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
                self.base_image_cache[image_path] = pil_image
            except Exception as e:
                logger.error(f"Error loading base image {image_path}: {e}")
                return None
        return self.base_image_cache[image_path]
    
    def get_scaled_image(self, image_path, target_width, target_height):
        """Get efficiently cached and scaled PhotoImage"""
        # Create cache key based on path and target dimensions
        cache_key = (image_path, target_width, target_height)
        
        # Return cached version if available
        if cache_key in self.scaled_image_cache:
            return self.scaled_image_cache[cache_key]
        
        # Load base image
        base_image = self.get_base_image(image_path)
        if base_image is None:
            return None
        
        try:
            # Use high-quality resampling for better results
            scaled_pil = base_image.resize((int(target_width), int(target_height)), Image.Resampling.LANCZOS)
            
            # Import ImageTk here to avoid circular imports
            from PIL import ImageTk
            photo_image = ImageTk.PhotoImage(scaled_pil)
            
            # Cache the result (with size limit)
            if len(self.scaled_image_cache) >= self.max_cache_size:
                # Remove oldest entries (simple FIFO)
                oldest_key = next(iter(self.scaled_image_cache))
                del self.scaled_image_cache[oldest_key]
            
            self.scaled_image_cache[cache_key] = photo_image
            return photo_image
            
        except Exception as e:
            logger.error(f"Error scaling image {image_path}: {e}")
            return None
    
    def rescale_images_optimized(self, zoom):
        """Optimized image rescaling with caching"""
        if not hasattr(self, 'image_refs'):
            return
        
        # Get all image items at once
        all_items = self.canvas.find_all()
        image_items = [item for item in all_items 
                      if self.canvas.type(item) == 'image' and 'image' in self.canvas.gettags(item)]
        
        # Batch process images
        updates = []
        for item in image_items:
            if item in self.original_image_sizes and item in self.image_refs:
                orig_width, orig_height = self.original_image_sizes[item]
                new_width = int(orig_width * zoom)
                new_height = int(orig_height * zoom)
                
                # Get the image path
                image_path = getattr(self.image_refs[item], 'image_path', None)
                if image_path and os.path.exists(image_path):
                    scaled_image = self.get_scaled_image(image_path, new_width, new_height)
                    if scaled_image:
                        updates.append((item, scaled_image))
        
        # Apply all updates at once
        for item, scaled_image in updates:
            self.canvas.itemconfig(item, image=scaled_image)
            self.image_refs[item] = scaled_image
        
        # Periodic cache cleanup to prevent memory issues
        if len(updates) > 0:  # Only cleanup when we actually processed images
            self.cleanup_image_cache()
    
    def check_for_updates(self):
        """Check for updates from GitHub releases"""
        logger.info("Checking for updates...")
        
        # Update status using root.after to ensure it's on the main thread
        self.root.after(0, lambda: self.update_status_safe("🔄 Checking for updates..."))
        
        # Run the update check in a separate thread to avoid blocking the UI
        def check_updates_thread():
            try:
                logger.info("Starting background update check...")
                # Fetch the latest release info from GitHub API
                url = "https://api.github.com/repos/BitEU/COMRADE/releases/latest"
                req = urllib.request.Request(url)
                req.add_header('User-Agent', f'COMRADE/{COMRADE_VERSION}')
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode())
                    latest_tag = data.get('tag_name', '').lstrip('v')  # Remove 'v' prefix if present
                    release_url = data.get('html_url', 'https://github.com/BitEU/COMRADE/releases')
                    
                    logger.info(f"Update check completed. Latest version: {latest_tag}")
                    # Schedule the UI update on the main thread
                    self.root.after(0, lambda: self.handle_version_check_result(latest_tag, release_url))
                    
            except urllib.error.URLError as e:
                logger.error(f"Network error checking for updates: {e}")
                self.root.after(0, lambda: self.handle_version_check_error("Network error"))
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error checking for updates: {e}")
                self.root.after(0, lambda: self.handle_version_check_error("Data parsing error"))
            except Exception as e:
                logger.error(f"Unexpected error checking for updates: {e}")
                self.root.after(0, lambda: self.handle_version_check_error("Unexpected error"))
        
        # Start the check in a background thread
        try:
            thread = threading.Thread(target=check_updates_thread, daemon=True)
            thread.start()
            logger.info("Background update check thread started successfully")
        except Exception as e:
            logger.error(f"Failed to start update check thread: {e}")
            self.root.after(0, lambda: self.handle_version_check_error("Failed to start update check"))
    
    def handle_version_check_result(self, latest_version, release_url):
        """Handle the result of version checking on the main thread"""
        current_version = COMRADE_VERSION
        
        logger.info(f"Current version: {current_version}, Latest version: {latest_version}")
        
        if self.is_newer_version(current_version, latest_version):
            logger.info("New version available!")
            self.update_status_safe(f"🔄 New version {latest_version} available!")
            # Show update dialog
            dialog = VersionUpdateDialog(self.root, current_version, latest_version, release_url)
            self.root.wait_window(dialog.dialog)
        else:
            logger.info("Already up to date")
            self.update_status_safe("✅ You're up to date!")
            # Show up-to-date dialog
            dialog = NoUpdateDialog(self.root, current_version)
            self.root.wait_window(dialog.dialog)
    
    def handle_version_check_error(self, error_type):
        """Handle version check errors on the main thread"""
        logger.error(f"Version check failed: {error_type}")
        self.update_status_safe(f"❌ Update check failed: {error_type}")
        messagebox.showerror(
            "Update Check Failed",
            f"Failed to check for updates: {error_type}\n\n"
            "Please check your internet connection and try again.\n"
            "You can also visit https://github.com/BitEU/COMRADE/releases manually.",
            parent=self.root
        )
    
    def is_newer_version(self, current, latest):
        """Compare version strings to determine if latest is newer than current"""
        try:
            # Parse version strings (e.g., "0.6.3" -> [0, 6, 3])
            current_parts = [int(x) for x in current.split('.')]
            latest_parts = [int(x) for x in latest.split('.')]
            
            # Pad the shorter version with zeros
            max_length = max(len(current_parts), len(latest_parts))
            current_parts.extend([0] * (max_length - len(current_parts)))
            latest_parts.extend([0] * (max_length - len(latest_parts)))
            
            # Compare part by part
            for i in range(max_length):
                if latest_parts[i] > current_parts[i]:
                    return True
                elif latest_parts[i] < current_parts[i]:
                    return False
            
            return False  # Versions are equal
            
        except (ValueError, AttributeError) as e:
            logger.error(f"Error comparing versions '{current}' and '{latest}': {e}")
            # If we can't parse versions, assume latest is newer to be safe
            return latest != current
    
    def update_status(self, message):
        """Update the status bar with a message"""
        if hasattr(self, 'status_label'):
            self.status_label.config(text=message)
            # Auto-clear status after 5 seconds if it's a temporary message
            if "🔗" in message or "✅" in message or "cancelled" in message:
                self.root.after(5000, lambda: self.update_status("Ready - Right-click a person to start linking"))
    
    def update_status_safe(self, message):
        """Thread-safe version of update_status that doesn't call update_idletasks"""
        if hasattr(self, 'status_label'):
            self.status_label.config(text=message)
            # Auto-clear status after 5 seconds if it's a temporary message
            if "🔗" in message or "✅" in message or "cancelled" in message or "❌" in message:
                self.root.after(5000, lambda: self.update_status_safe("Ready - Right-click a person to start linking"))
    
    def check_for_updates_silently(self):
        """Silently check for updates on startup - only show dialog if update is available"""
        logger.info("Silently checking for updates on startup...")
        
        # Run the update check in a separate thread to avoid blocking the UI
        def check_updates_thread():
            try:
                # Fetch the latest release info from GitHub API
                url = "https://api.github.com/repos/BitEU/COMRADE/releases/latest"
                req = urllib.request.Request(url)
                req.add_header('User-Agent', f'COMRADE/{COMRADE_VERSION}')
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode())
                    latest_tag = data.get('tag_name', '').lstrip('v')  # Remove 'v' prefix if present
                    release_url = data.get('html_url', 'https://github.com/BitEU/COMRADE/releases')
                    
                    # Schedule the UI update on the main thread
                    self.root.after(0, lambda: self.handle_silent_version_check_result(latest_tag, release_url))
                    
            except Exception as e:
                # Silently log errors - don't show error dialogs on startup
                logger.debug(f"Silent update check failed: {e}")
        
        # Start the check in a background thread
        thread = threading.Thread(target=check_updates_thread, daemon=True)
        thread.start()
    
    def handle_silent_version_check_result(self, latest_version, release_url):
        """Handle the result of silent version checking - only show dialog if update available"""
        current_version = COMRADE_VERSION
        
        logger.info(f"Silent check - Current version: {current_version}, Latest version: {latest_version}")
        
        if self.is_newer_version(current_version, latest_version):
            logger.info("New version available - showing update dialog")
            # Show update dialog only if new version is available
            dialog = VersionUpdateDialog(self.root, current_version, latest_version, release_url)
            self.root.wait_window(dialog.dialog)
        else:
            logger.info("Already up to date - no dialog shown")

if __name__ == "__main__":
    logger.info("Starting application")
    root = tk.Tk()
    logger.info("Tkinter root created")
    app = ConnectionApp(root)
    logger.info("Starting main loop")
    root.mainloop()
    logger.info("Application ended")