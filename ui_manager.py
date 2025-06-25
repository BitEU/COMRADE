# ui_manager.py
"""
UI Manager - Handles user interface creation and updates
"""

import tkinter as tk
from tkinter import ttk
import logging
from constants import COLORS

logger = logging.getLogger(__name__)

class UIManager:
    """Manages the user interface elements"""
    
    def __init__(self, app):
        self.app = app
        self.status_label = None
        self.zoom_slider = None
        self.zoom_var = tk.DoubleVar(value=1.0)
        
    def create_ui(self, parent):
        """Create the main user interface"""
        # Configure styles
        self.setup_styles()
        
        # Header
        header_frame = self.create_header(parent)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Toolbar
        toolbar_frame = self.create_toolbar(parent)
        toolbar_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Canvas frame
        canvas_frame = ttk.Frame(parent)
        canvas_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create canvas
        canvas = tk.Canvas(
            canvas_frame,
            bg=COLORS['surface'],
            highlightthickness=0,
            relief=tk.FLAT
        )
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # Instructions
        instructions_frame = self.create_instructions(parent)
        instructions_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Status bar
        status_frame = self.create_status_bar(parent)
        status_frame.pack(fill=tk.X)
        
        return canvas
    
    def setup_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        
        # Configure frame style
        style.configure("Header.TFrame", background=COLORS['background'])
        style.configure("Toolbar.TFrame", background=COLORS['background'])
        
        # Configure label style  
        style.configure("Title.TLabel", 
            font=("Segoe UI", 20, "bold"),
            foreground=COLORS['primary'],
            background=COLORS['background']
        )
        
        style.configure("Status.TLabel",
            font=("Segoe UI", 9),
            foreground=COLORS['text_secondary'],
            background=COLORS['background']
        )
        
        style.configure("Instructions.TLabel",
            font=("Segoe UI", 9),
            foreground=COLORS['text_secondary'],
            background=COLORS['background']
        )
    
    def create_header(self, parent):
        """Create header section"""
        frame = ttk.Frame(parent, style="Header.TFrame")
        
        title = ttk.Label(
            frame,
            text="People Connection Visualizer",
            style="Title.TLabel"
        )
        title.pack(side=tk.LEFT, padx=(0, 20))
        
        subtitle = ttk.Label(
            frame,
            text="Visualize and organize relationships",
            font=("Segoe UI", 11),
            foreground=COLORS['text_secondary'],
            background=COLORS['background']
        )
        subtitle.pack(side=tk.LEFT)
        
        return frame
    
    def create_toolbar(self, parent):
        """Create toolbar with action buttons"""
        frame = ttk.Frame(parent, style="Toolbar.TFrame")
          # Button configurations
        buttons = [
            ("👤 Add Person", self.app.add_person, COLORS['primary']),
            ("💾 Save", self.app.save_data, COLORS['success']),
            ("📁 Load", self.app.load_data, COLORS['accent']),
            ("🖼️ Export PNG", self.app.export_to_png, COLORS['secondary']),
            ("🗑️ Clear All", self.app.clear_all, COLORS['danger'])
        ]
        
        for text, command, color in buttons:
            btn = self.create_button(frame, text, command, color)
            btn.pack(side=tk.LEFT, padx=(0, 10))
        
        return frame
    
    def create_button(self, parent, text, command, bg_color):
        """Create a modern styled button"""
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI", 10, "bold"),
            bg=bg_color,
            fg='white',
            relief=tk.FLAT,
            padx=20,
            pady=10,
            cursor='hand2',
            activebackground=self.darken_color(bg_color),
            activeforeground='white'
        )
        
        # Add hover effects
        btn.bind("<Enter>", lambda e: btn.config(bg=self.darken_color(bg_color)))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg_color))
        
        return btn
    
    def create_instructions(self, parent):
        """Create instructions panel"""
        frame = ttk.Frame(parent, style="Toolbar.TFrame")
        
        instructions = [
            "🖱️ Left-click: Select and drag",
            "🖱️ Right-click: Create connections",
            "🖱️ Double-click: Edit person/connection",
            "🖱️ Middle-drag: Pan canvas",
            "🖱️ Scroll: Zoom in/out",
            "⌨️ Escape: Cancel connection",
            "⌨️ Delete: Remove selected"
        ]
        
        for i, instruction in enumerate(instructions):
            label = ttk.Label(
                frame,
                text=instruction,
                style="Instructions.TLabel"
            )
            label.pack(side=tk.LEFT, padx=(0, 20) if i < len(instructions)-1 else 0)
        
        return frame
    
    def create_status_bar(self, parent):
        """Create status bar with zoom control"""
        frame = ttk.Frame(parent, style="Toolbar.TFrame")
        
        # Status label
        self.status_label = ttk.Label(
            frame,
            text="Ready",
            style="Status.TLabel"
        )
        self.status_label.pack(side=tk.LEFT, padx=(0, 20))
        
        # Zoom controls
        zoom_label = ttk.Label(
            frame,
            text="Zoom:",
            style="Status.TLabel"
        )
        zoom_label.pack(side=tk.RIGHT, padx=(0, 5))
        
        self.zoom_slider = ttk.Scale(
            frame,
            from_=0.1,
            to=3.0,
            orient=tk.HORIZONTAL,
            variable=self.zoom_var,
            command=self.on_zoom_change,
            length=150
        )
        self.zoom_slider.pack(side=tk.RIGHT, padx=(0, 10))
        
        zoom_percent_label = ttk.Label(
            frame,
            textvariable=self.create_zoom_percent_var(),
            style="Status.TLabel"
        )
        zoom_percent_label.pack(side=tk.RIGHT, padx=(0, 10))
        
        return frame
    
    def create_zoom_percent_var(self):
        """Create a StringVar that shows zoom percentage"""
        var = tk.StringVar()
        
        def update_percent(*args):
            var.set(f"{int(self.zoom_var.get() * 100)}%")
        
        self.zoom_var.trace('w', update_percent)
        update_percent()
        
        return var
    
    def on_zoom_change(self, value):
        """Handle zoom slider change"""
        if self.app.canvas_manager:
            self.app.canvas_manager.set_zoom(float(value))
    
    def update_zoom_slider(self, zoom_level):
        """Update zoom slider to match current zoom"""
        self.zoom_var.set(zoom_level)
    
    def update_status(self, message):
        """Update status bar message"""
        if self.status_label:
            self.status_label.config(text=message)
            
            # Auto-clear temporary messages after 5 seconds
            if any(indicator in message for indicator in ["✅", "Connected", "Added", "Updated", "Deleted"]):
                self.app.root.after(5000, lambda: self.update_status("Ready"))
    
    def darken_color(self, color):
        """Darken a hex color by 20%"""
        # Remove # if present
        color = color.lstrip('#')
        
        # Convert to RGB
        rgb = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        
        # Darken by 20%
        darkened = tuple(int(c * 0.8) for c in rgb)
        
        # Convert back to hex
        return '#%02x%02x%02x' % darkened