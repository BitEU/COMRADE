import tkinter as tk
import os
from functools import lru_cache
import logging

from src.constants import COLORS, CARD_COLORS

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# This file will contain canvas helper functions.

class CanvasHelpers:
    def __init__(self, app):
        self.app = app

    def store_text_font_size(self, item_id, font_tuple):
        """Store the original font size for a text item."""
        if item_id not in self.app.original_font_sizes:
            self.app.original_font_sizes[item_id] = font_tuple[1]

    @lru_cache(maxsize=100)
    def get_scaled_image(self, image_path, width, height):
        """
        Get a scaled and cached PhotoImage.
        Uses LRU cache for performance.
        """
        if not PIL_AVAILABLE or not os.path.exists(image_path):
            return None
        try:
            # Open the base image (cached)
            if image_path not in self.app.base_image_cache:
                self.app.base_image_cache[image_path] = Image.open(image_path)
            
            base_image = self.app.base_image_cache[image_path]
            
            # Resize
            resized_image = base_image.resize((width, height), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(resized_image)
            return photo
        except Exception as e:
            logger.error(f"Failed to get scaled image for {image_path}: {e}")
            return None

    def rescale_images(self, zoom):
        """Rescale all image items on the canvas based on their original dimensions"""
        if not hasattr(self.app, 'image_refs'):
            return
        
        image_items = [item for item in self.app.canvas.find_all() if self.app.canvas.type(item) == 'image' and 'image' in self.app.canvas.gettags(item)]
        
        for item in image_items:
            if item in self.app.original_image_sizes and item in self.app.image_refs:
                original_width, original_height = self.app.original_image_sizes[item]
                new_width = max(10, int(original_width * zoom))
                new_height = max(10, int(original_height * zoom))
                
                tags = self.app.canvas.gettags(item)
                person_tag = next((tag for tag in tags if tag.startswith('person_')), None)
                
                if person_tag:
                    person_id = int(person_tag.split('_')[1])
                    if person_id in self.app.people:
                        person = self.app.people[person_id]
                        
                        image_file = None
                        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
                        if hasattr(person, 'files') and person.files:
                            image_file = next((fp for fp in person.files if os.path.exists(fp) and os.path.splitext(fp.lower())[1] in image_extensions), None)

                        if image_file and PIL_AVAILABLE:
                            try:
                                new_photo = self.get_scaled_image(image_file, new_width, new_height)
                                if new_photo:
                                    self.app.canvas.itemconfig(item, image=new_photo)
                                    self.app.image_refs[item] = new_photo
                            except Exception as e:
                                logger.warning(f"Failed to rescale image for person {person_id}: {e}")

    def rescale_text(self, zoom):
        # Rescale all text items on the canvas based on their original font sizes
        text_items = [item for item in self.app.canvas.find_all() if self.app.canvas.type(item) == 'text']
        
        for item in text_items:
            if item not in self.app.original_font_sizes:
                current_font = self.app.canvas.itemcget(item, 'font')
                parts = current_font.split()
                base_size = next((int(p) for p in parts if p.isdigit()), 10)
                self.app.original_font_sizes[item] = base_size
            
            original_size = self.app.original_font_sizes[item]
            new_size = max(6, int(original_size * zoom))
            
            current_font = self.app.canvas.itemcget(item, 'font')
            parts = current_font.split()
            
            if len(parts) >= 2:
                size_index = next((i for i, p in enumerate(parts) if p.isdigit()), -1)
                if size_index != -1:
                    parts[size_index] = str(new_size)
                    new_font = ' '.join(parts)
                else:
                    new_font = f"Segoe UI {new_size}"
            else:
                new_font = f"Segoe UI {new_size}"
            
            self.app.canvas.itemconfig(item, font=new_font)

    def redraw_grid(self):
        self.app.canvas.delete("grid")
        width = self.app.fixed_canvas_width
        height = self.app.fixed_canvas_height
        grid_size = 40 * (self.app.events.last_zoom if hasattr(self.app.events, 'last_zoom') else 1)
        
        min_grid_spacing = 20
        if grid_size < min_grid_spacing:
            grid_size = min_grid_spacing
        
        x_step = max(int(grid_size), 40)
        for x in range(0, int(width + x_step), x_step):
            self.app.canvas.create_line(x, 0, x, height, fill='#e2e8f0', width=1, tags="grid")
        
        y_step = max(int(grid_size), 40)
        for y in range(0, int(height + y_step), y_step):
            self.app.canvas.create_line(0, y, width, y, fill='#e2e8f0', width=1, tags="grid")
        
        self.app.canvas.tag_lower("grid")

    def update_connections(self):
        """Redraw all connection lines based on current person positions and zoom"""
        zoom = self.app.events.last_zoom
        
        # Clear all existing lines and labels first
        for key, elements in list(self.app.connection_lines.items()):
            if len(elements) == 4:
                line_id, label_id, clickable_area_id, bg_rect_id = elements
                self.app.canvas.delete(line_id)
                if label_id:
                    self.app.canvas.delete(label_id)
                if bg_rect_id:
                    self.app.canvas.delete(bg_rect_id)
                if clickable_area_id:
                    self.app.canvas.delete(clickable_area_id)
            elif len(elements) == 3: # Backwards compatibility
                line_id, label_id, clickable_area_id = elements[:3]
                self.app.canvas.delete(line_id)
                if label_id:
                    # Delete the label and its background group
                    group_tag = f"connection_label_group_{key[0]}_{key[1]}"
                    self.app.canvas.delete(group_tag)
                    self.app.canvas.delete(label_id)
                if clickable_area_id:
                    self.app.canvas.delete(clickable_area_id)

        self.app.connection_lines.clear()

        # Redraw all connections
        # Check connections from people
        for id1, p1 in self.app.people.items():
            for id2, label in p1.connections.items():
                if id2 in self.app.people or id2 in self.app.textboxes:
                    # Ensure we only draw each connection once
                    if id1 < id2:
                        self.draw_connection(id1, id2, label, zoom)
        
        # Check connections from textboxes (to avoid duplication, only check textbox-to-textbox with higher ID)
        for id1, t1 in self.app.textboxes.items():
            for id2, label in t1.connections.items():
                if id2 in self.app.textboxes and id1 < id2:
                    self.draw_connection(id1, id2, label, zoom)
        
        # Check connections from legend cards
        for id1, l1 in self.app.legends.items():
            for id2, label in l1.connections.items():
                if id2 in self.app.legends and id1 < id2:
                    self.draw_connection(id1, id2, label, zoom)

    def draw_connection(self, id1, id2, label, zoom=1.0):
        """Draw a single connection line and its label, scaled by zoom"""
        # Get card objects (could be person, textbox, or legend)
        card1 = self.app.people.get(id1) or self.app.textboxes.get(id1) or self.app.legends.get(id1)
        card2 = self.app.people.get(id2) or self.app.textboxes.get(id2) or self.app.legends.get(id2)
        
        if not card1 or not card2:
            return
        
        # Get scaled coordinates
        x1, y1 = card1.x * zoom, card1.y * zoom
        x2, y2 = card2.x * zoom, card2.y * zoom
        
        # Create the main line
        line = self.app.canvas.create_line(x1, y1, x2, y2, fill=COLORS['text_secondary'], width=2, tags=("connection", f"connection_{id1}_{id2}"))
        
        # Create a thicker, transparent line for easier clicking
        clickable_area = self.app.canvas.create_line(x1, y1, x2, y2, fill="", width=10, tags=("connection_clickable", f"connection_clickable_{id1}_{id2}"))
        
        label_id = None
        bg_rect_id = None
        if label:
            # Calculate midpoint for the label
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            
            # Create a background for the label for better readability
            font_size = max(8, int(10 * zoom))
            label_font = ("Segoe UI", font_size)
            
            # Create the text label
            label_id = self.app.canvas.create_text(mid_x, mid_y, text=label, 
                                             font=label_font, 
                                             fill=COLORS['text_primary'], 
                                             tags=("connection_label", f"connection_label_{id1}_{id2}"))
            
            # Get bounding box of the text to create a background
            bbox = self.app.canvas.bbox(label_id)
            if bbox:
                # Create a rectangle behind the text with padding
                x1_bbox, y1_bbox, x2_bbox, y2_bbox = bbox
                padding = 5 * zoom
                bg_rect_id = self.app.canvas.create_rectangle(x1_bbox - padding, y1_bbox - padding, x2_bbox + padding, y2_bbox + padding, 
                                                        fill=COLORS['surface'], 
                                                        outline='#e0e0e0', 
                                                        width=1,
                                                        tags=(f"connection_label_bg_{id1}_{id2}",))

            # Store original font size for scaling
            if label_id:
                self.store_text_font_size(label_id, ("Segoe UI", 10))

        # Store all parts of the connection
        self.app.connection_lines[(min(id1, id2), max(id1, id2))] = (line, label_id, clickable_area, bg_rect_id)
        
        # Ensure grid stays at the very bottom
        self.app.canvas.tag_lower("grid")

        # After creating all elements, ensure proper layering
        self.app.canvas.tag_lower(line)
        if clickable_area:
            self.app.canvas.tag_lower(clickable_area)

        if bg_rect_id:
            self.app.canvas.tag_lower(bg_rect_id, line) # ensure bg is below line
            self.app.canvas.tag_raise(bg_rect_id) # then raise it
        if label_id:
            self.app.canvas.tag_lower(label_id, line) # ensure label is below line
            self.app.canvas.tag_raise(label_id) # then raise it
        
        if bg_rect_id and label_id:
            self.app.canvas.tag_raise(label_id, bg_rect_id)

        # Ensure person, textbox, and legend widgets are on top of lines
        self.app.canvas.tag_raise("person")
        self.app.canvas.tag_raise("textbox")
        self.app.canvas.tag_raise("legend")
    
    def add_grid_pattern(self):
        canvas_width = self.app.fixed_canvas_width
        canvas_height = self.app.fixed_canvas_height
        grid_size = 40
        
        for x in range(0, canvas_width, grid_size):
            self.app.canvas.create_line(x, 0, x, canvas_height, fill='#e2e8f0', width=1, tags="grid")
        
        for y in range(0, canvas_height, grid_size):
            self.app.canvas.create_line(0, y, canvas_width, y, fill='#e2e8f0', width=1, tags="grid")
        
        self.app.canvas.tag_lower("grid")

    def create_person_widget(self, person_id, zoom=None):
        if self.app.events.dragging:
            logger.warning(f"Attempted to create widget for person {person_id} during drag - skipping")
            return
            
        logger.info(f"Creating modern widget for person {person_id}")
        person = self.app.people[person_id]
        if zoom is None:
            zoom = self.app.events.last_zoom if hasattr(self.app.events, 'last_zoom') else 1.0

        if not hasattr(person, 'base_x'):
            person.base_x = person.x
            person.base_y = person.y
        x = person.x * zoom
        y = person.y * zoom
        
        group = []
        
        info_lines = [
            f"👤 {person.name}" if person.name else "👤 Unnamed",
            f"🎂 {person.dob}" if person.dob else "",
            f"🏷️ {person.alias}" if person.alias else "",
            f"🏠 {person.address}" if person.address else "",
            f"📞 {person.phone}" if person.phone else ""
        ]
        info_lines = [line for line in info_lines if line.strip()]
        
        image_file = None
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        if hasattr(person, 'files') and person.files:
            image_file = next((fp for fp in person.files if os.path.exists(fp) and os.path.splitext(fp.lower())[1] in image_extensions), None)

        base_width = max(max(len(line) for line in info_lines) * 9 if info_lines else 0, 200)
        image_width = 120 if image_file else 0
        card_width = (base_width + image_width + (20 if image_file else 0)) * zoom
        card_height = max(len(info_lines) * 25 + 40, 120, 140 if image_file else 120) * zoom
        
        half_width = card_width // 2
        half_height = card_height // 2
        
        shadow_offset = int(3 * zoom)
        for i in range(3, 0, -1):
            shadow_color = '#e0e0e0' if i == 3 else ('#d0d0d0' if i == 2 else '#c0c0c0')
            shadow = self.app.canvas.create_rectangle(
                x - half_width + i, y - half_height + i,
                x + half_width + i, y + half_height + i,
                fill=shadow_color, outline='', width=0,
                tags=(f"person_{person_id}", "person", "shadow")
            )
            group.append(shadow)

        person_color = CARD_COLORS[person.color % len(CARD_COLORS)]
        
        main_card = self.app.canvas.create_rectangle(
            x - half_width, y - half_height, x + half_width, y + half_height,
            fill=COLORS['surface'], outline=person_color, width=2,
            tags=(f"person_{person_id}", "person")
        )
        group.append(main_card)
        
        header_height = int(30 * zoom)
        header = self.app.canvas.create_rectangle(
            x - half_width, y - half_height, x + half_width, y - half_height + header_height,
            fill=person_color, outline='', width=0,
            tags=(f"person_{person_id}", "person")
        )
        group.append(header)
        
        avatar_size = int(20 * zoom)
        avatar_x = x - half_width + int(15 * zoom)
        avatar_y = y - half_height + int(15 * zoom)

        avatar_bg = self.app.canvas.create_oval(
            avatar_x - avatar_size//2, avatar_y - avatar_size//2,
            avatar_x + avatar_size//2, avatar_y + avatar_size//2,
            fill='white', outline=person_color, width=2,
            tags=(f"person_{person_id}", "person")
        )
        group.append(avatar_bg)

        avatar_icon = self.app.canvas.create_text(
            avatar_x, avatar_y, text="👤",
            font=("Arial", int(10 * zoom)), fill=person_color,
            tags=(f"person_{person_id}", "person")
        )
        self.store_text_font_size(avatar_icon, ("Arial", 10))
        group.append(avatar_icon)

        name_text = self.app.canvas.create_text(
            avatar_x + avatar_size + int(10 * zoom), avatar_y,
            text=person.name or "Unnamed",
            anchor="w", font=("Segoe UI", int(11 * zoom), "bold"), 
            fill='white',
            tags=(f"person_{person_id}", "person")
        )
        self.store_text_font_size(name_text, ("Segoe UI", 11, "bold"))
        group.append(name_text)

        if getattr(person, 'files', []):
            file_icon = self.app.canvas.create_text(
                avatar_x + avatar_size + int(10 * zoom) + int(8 * zoom) + self.app.canvas.bbox(name_text)[2] - self.app.canvas.bbox(name_text)[0],
                avatar_y,
                text="📎",
                anchor="w", font=("Segoe UI Emoji", int(10 * zoom)),
                fill='white',
                tags=(f"person_{person_id}", "person", "file_icon")
            )
            self.store_text_font_size(file_icon, ("Segoe UI Emoji", 10))
            group.append(file_icon)

        details_start_y = y - half_height + header_height + int(15 * zoom)
        line_height = int(20 * zoom)
        
        details = [("🎂", person.dob), ("🏷️", person.alias), ("🏠", person.address), ("📞", person.phone)]
        
        current_y = details_start_y
        icon_x = x - half_width + int(15 * zoom)
        text_x = icon_x + int(25 * zoom)
        
        for icon, value in details:
            if value and value.strip():
                icon_item = self.app.canvas.create_text(
                    icon_x, current_y, text=icon, anchor="nw", font=("Segoe UI Emoji", int(9 * zoom)),
                    fill=COLORS['text_primary'], tags=(f"person_{person_id}", "person")
                )
                self.store_text_font_size(icon_item, ("Segoe UI Emoji", 9))
                text_item = self.app.canvas.create_text(
                    text_x, current_y, text=value, anchor="nw", font=("Segoe UI", int(9 * zoom)),
                    fill=COLORS['text_primary'], tags=(f"person_{person_id}", "person")
                )
                self.store_text_font_size(text_item, ("Segoe UI", 9))
                group.extend([icon_item, text_item])
                current_y += line_height
        
        if image_file and PIL_AVAILABLE:
            try:
                base_max_width, base_max_height = 100, 100
                pil_image = Image.open(image_file)
                img_ratio = pil_image.width / pil_image.height
                if base_max_width / base_max_height > img_ratio:
                    base_img_height = base_max_height
                    base_img_width = int(base_img_height * img_ratio)
                else:
                    base_img_width = base_max_width
                    base_img_height = int(base_img_width / img_ratio)
                
                img_width, img_height = int(base_img_width * zoom), int(base_img_height * zoom)
                
                photo = self.get_scaled_image(image_file, img_width, img_height)
                
                if photo:
                    img_x = x + half_width - img_width//2 - int(10 * zoom)
                    img_y = y - half_height + header_height + img_height//2 + int(10 * zoom)
                    
                    img_item = self.app.canvas.create_image(
                        img_x, img_y, image=photo, anchor="center",
                        tags=(f"person_{person_id}", "person", "image")
                    )
                    
                    if not hasattr(self.app, 'image_refs'):
                        self.app.image_refs = {}
                    self.app.image_refs[img_item] = photo
                    
                    self.app.original_image_sizes[img_item] = (base_img_width, base_img_height)
                    group.append(img_item)
            except Exception as e:
                logger.error(f"Failed to load image {image_file}: {e}")
        
        self.app.person_widgets[person_id] = group
        
        for item in group:
            self.app.canvas.tag_bind(item, "<Double-Button-1>", lambda e, pid=person_id: self.app.events.edit_person(pid))
        
        self.add_hover_effects(person_id, group)
        logger.info(f"Modern widget creation complete for person {person_id}")

    def add_hover_effects(self, person_id, group):
        def on_enter(event):
            if self.app.events.connecting and self.app.events.connection_start == person_id:
                return
            for item in group:
                if 'shadow' not in self.app.canvas.gettags(item) and 'corner' not in self.app.canvas.gettags(item):
                    if self.app.canvas.type(item) == 'rectangle':
                        self.app.canvas.itemconfig(item, outline=COLORS['primary'], width=3)
        
        def on_leave(event):
            if self.app.events.connecting and self.app.events.connection_start == person_id:
                return
            person = self.app.people[person_id]
            person_color = CARD_COLORS[person.color % len(CARD_COLORS)]
            for item in group:
                if 'shadow' not in self.app.canvas.gettags(item) and 'corner' not in self.app.canvas.gettags(item):
                    if self.app.canvas.type(item) == 'rectangle':
                        self.app.canvas.itemconfig(item, outline=person_color, width=2)

        for item in group:
            self.app.canvas.tag_bind(item, "<Enter>", on_enter)
            self.app.canvas.tag_bind(item, "<Leave>", on_leave)

    def highlight_card_for_connection(self, card_id):
        """Highlight a card (person, textbox, or legend) for connection"""
        if card_id in self.app.people:
            self.highlight_person_for_connection(card_id)
        elif card_id in self.app.textboxes:
            self.highlight_textbox_for_connection(card_id)
        elif card_id in self.app.legends:
            self.highlight_legend_for_connection(card_id)
    
    def unhighlight_card_for_connection(self, card_id):
        """Unhighlight a card (person, textbox, or legend) for connection"""
        if card_id in self.app.people:
            self.unhighlight_person_for_connection(card_id)
        elif card_id in self.app.textboxes:
            self.unhighlight_textbox_for_connection(card_id)
        elif card_id in self.app.legends:
            self.unhighlight_legend_for_connection(card_id)

    def highlight_textbox_for_connection(self, textbox_id):
        """Highlight a textbox for connection"""
        group = self.app.textbox_widgets.get(textbox_id, [])
        textbox_color = CARD_COLORS[self.app.textboxes[textbox_id].color % len(CARD_COLORS)]
        
        for item in group:
            tags = self.app.canvas.gettags(item)
            if 'shadow' in tags:
                continue
            
            item_type = self.app.canvas.type(item)
            if item_type == 'rectangle':
                # Header
                if self.app.canvas.itemcget(item, 'fill') == textbox_color:
                     self.app.canvas.itemconfig(item, fill=COLORS['accent'])
                # Main card
                else:
                     self.app.canvas.itemconfig(item, fill=COLORS['surface_bright'])

    def unhighlight_textbox_for_connection(self, textbox_id):
        """Unhighlight a textbox for connection"""
        group = self.app.textbox_widgets.get(textbox_id, [])
        textbox = self.app.textboxes[textbox_id]
        textbox_color = CARD_COLORS[textbox.color % len(CARD_COLORS)]

        for item in group:
            tags = self.app.canvas.gettags(item)
            if 'shadow' in tags:
                continue

            item_type = self.app.canvas.type(item)
            if item_type == 'rectangle':
                # Header
                if self.app.canvas.itemcget(item, 'fill') == COLORS['accent']:
                    self.app.canvas.itemconfig(item, fill=textbox_color)
                # Main card
                else:
                    self.app.canvas.itemconfig(item, fill=COLORS['surface'])

    def create_textbox_widget(self, textbox_id, zoom=None):
        """Create a textbox card widget on the canvas"""
        if self.app.events.dragging:
            logger.warning(f"Attempted to create widget for textbox {textbox_id} during drag - skipping")
            return
            
        logger.info(f"Creating widget for textbox {textbox_id}")
        textbox = self.app.textboxes[textbox_id]
        if zoom is None:
            zoom = self.app.events.last_zoom if hasattr(self.app.events, 'last_zoom') else 1.0

        if not hasattr(textbox, 'base_x'):
            textbox.base_x = textbox.x
            textbox.base_y = textbox.y
        x = textbox.x * zoom
        y = textbox.y * zoom
        
        group = []
        
        # Calculate card dimensions based on content
        title_width = len(textbox.title) * 10 if textbox.title else 100
        
        # For content, we'll use a fixed width for wrapping and calculate height based on wrapped lines
        content_char_width = 70  # Characters per line for wrapping
        wrapped_lines = []
        if textbox.content:
            content_lines = textbox.content.split('\n')
            for line in content_lines:
                if len(line) <= content_char_width:
                    wrapped_lines.append(line)
                else:
                    # Wrap long lines
                    words = line.split(' ')
                    current_line = ''
                    for word in words:
                        if len(current_line + word) <= content_char_width:
                            current_line += word + ' '
                        else:
                            if current_line:
                                wrapped_lines.append(current_line.strip())
                            current_line = word + ' '
                    if current_line:
                        wrapped_lines.append(current_line.strip())
        
        base_width = max(title_width, content_char_width * 8, 250)
        base_height = max(120, 50 + len(wrapped_lines) * 20)
        
        card_width = base_width * zoom
        card_height = base_height * zoom
        
        half_width = card_width // 2
        half_height = card_height // 2
        
        # Create shadow effect
        shadow_offset = int(3 * zoom)
        for i in range(3, 0, -1):
            shadow_color = '#e0e0e0' if i == 3 else ('#d0d0d0' if i == 2 else '#c0c0c0')
            shadow = self.app.canvas.create_rectangle(
                x - half_width + i, y - half_height + i,
                x + half_width + i, y + half_height + i,
                fill=shadow_color, outline='', width=0,
                tags=(f"textbox_{textbox_id}", "textbox", "shadow")
            )
            group.append(shadow)

        textbox_color = CARD_COLORS[textbox.color % len(CARD_COLORS)]
        
        # Main card
        main_card = self.app.canvas.create_rectangle(
            x - half_width, y - half_height, x + half_width, y + half_height,
            fill=COLORS['surface'], outline=textbox_color, width=2,
            tags=(f"textbox_{textbox_id}", "textbox")
        )
        group.append(main_card)
        
        # Header
        header_height = int(35 * zoom)
        header = self.app.canvas.create_rectangle(
            x - half_width, y - half_height, x + half_width, y - half_height + header_height,
            fill=textbox_color, outline='', width=0,
            tags=(f"textbox_{textbox_id}", "textbox")
        )
        group.append(header)
        
        # Icon and title in header
        icon_x = x - half_width + int(15 * zoom)
        icon_y = y - half_height + int(17 * zoom)
        
        # Document icon
        icon = self.app.canvas.create_text(
            icon_x, icon_y, text="📝",
            font=("Segoe UI Emoji", int(12 * zoom)), fill='white',
            tags=(f"textbox_{textbox_id}", "textbox")
        )
        self.store_text_font_size(icon, ("Segoe UI Emoji", 12))
        group.append(icon)

        # Title text
        title_text = self.app.canvas.create_text(
            icon_x + int(25 * zoom), icon_y,
            text=textbox.title or "Untitled",
            anchor="w", font=("Segoe UI", int(12 * zoom), "bold"), 
            fill='white',
            tags=(f"textbox_{textbox_id}", "textbox")
        )
        self.store_text_font_size(title_text, ("Segoe UI", 12, "bold"))
        group.append(title_text)

        # Content area
        if textbox.content:
            content_start_y = y - half_height + header_height + int(15 * zoom)
            content_x = x - half_width + int(15 * zoom)
            
            # Use wrapped lines for display
            line_height = int(18 * zoom)
            
            # Limit display to 8 lines for the card
            display_lines = wrapped_lines[:8]
            
            for i, line in enumerate(display_lines):
                if line.strip():  # Only show non-empty lines
                    line_y = content_start_y + (i * line_height)
                    
                    content_item = self.app.canvas.create_text(
                        content_x, line_y, text=line, anchor="nw", 
                        font=("Segoe UI", int(10 * zoom)),
                        fill=COLORS['text_primary'], 
                        tags=(f"textbox_{textbox_id}", "textbox")
                    )
                    self.store_text_font_size(content_item, ("Segoe UI", 10))
                    group.append(content_item)
            
            # Show "..." if there are more lines
            if len(wrapped_lines) > 8:
                more_text = self.app.canvas.create_text(
                    content_x, content_start_y + (8 * line_height), 
                    text="...", anchor="nw", 
                    font=("Segoe UI", int(10 * zoom), "italic"),
                    fill=COLORS['text_secondary'], 
                    tags=(f"textbox_{textbox_id}", "textbox")
                )
                self.store_text_font_size(more_text, ("Segoe UI", 10, "italic"))
                group.append(more_text)

        self.app.textbox_widgets[textbox_id] = group
        
        # Add event bindings
        for item in group:
            self.app.canvas.tag_bind(item, "<Double-Button-1>", 
                                   lambda e, tid=textbox_id: self.app.events.edit_textbox(tid))
        
        self.add_textbox_hover_effects(textbox_id, group)
        logger.info(f"Widget creation complete for textbox {textbox_id}")

    def add_textbox_hover_effects(self, textbox_id, group):
        """Add hover effects to textbox widgets"""
        def on_enter(event):
            if self.app.events.connecting and self.app.events.connection_start == textbox_id:
                return
            for item in group:
                if 'shadow' not in self.app.canvas.gettags(item):
                    if self.app.canvas.type(item) == 'rectangle':
                        self.app.canvas.itemconfig(item, outline=COLORS['primary'], width=3)
        
        def on_leave(event):
            if self.app.events.connecting and self.app.events.connection_start == textbox_id:
                return
            textbox = self.app.textboxes[textbox_id]
            textbox_color = CARD_COLORS[textbox.color % len(CARD_COLORS)]
            for item in group:
                if 'shadow' not in self.app.canvas.gettags(item):
                    if self.app.canvas.type(item) == 'rectangle':
                        self.app.canvas.itemconfig(item, outline=textbox_color, width=2)
        
        for item in group:
            self.app.canvas.tag_bind(item, "<Enter>", on_enter)
            self.app.canvas.tag_bind(item, "<Leave>", on_leave)

    def highlight_person_for_connection(self, person_id):
        """Highlight a person for connection"""
        group = self.app.person_widgets.get(person_id, [])
        person_color = CARD_COLORS[self.app.people[person_id].color % len(CARD_COLORS)]
        
        for item in group:
            tags = self.app.canvas.gettags(item)
            if 'shadow' in tags:
                continue
            
            item_type = self.app.canvas.type(item)
            if item_type == 'rectangle':
                # Header
                if self.app.canvas.itemcget(item, 'fill') == person_color:
                     self.app.canvas.itemconfig(item, fill=COLORS['accent'])
                # Main card
                else:
                     self.app.canvas.itemconfig(item, fill=COLORS['surface_bright'])

    def unhighlight_person_for_connection(self, person_id):
        """Unhighlight a person for connection"""
        group = self.app.person_widgets.get(person_id, [])
        person = self.app.people[person_id]
        person_color = CARD_COLORS[person.color % len(CARD_COLORS)]

        for item in group:
            tags = self.app.canvas.gettags(item)
            if 'shadow' in tags:
                continue

            item_type = self.app.canvas.type(item)
            if item_type == 'rectangle':
                # Header
                if self.app.canvas.itemcget(item, 'fill') == COLORS['accent']:
                    self.app.canvas.itemconfig(item, fill=person_color)
                # Main card
                else:
                    self.app.canvas.itemconfig(item, fill=COLORS['surface'])

    def create_legend_widget(self, legend_id, zoom=None):
        """Create a legend card widget on the canvas"""
        if self.app.events.dragging:
            logger.warning(f"Attempted to create widget for legend {legend_id} during drag - skipping")
            return
            
        logger.info(f"Creating widget for legend {legend_id}")
        legend = self.app.legends[legend_id]
        if zoom is None:
            zoom = self.app.events.last_zoom if hasattr(self.app.events, 'last_zoom') else 1.0

        if not hasattr(legend, 'base_x'):
            legend.base_x = legend.x
            legend.base_y = legend.y
        x = legend.x * zoom
        y = legend.y * zoom
        
        group = []
        
        # Calculate card dimensions based on legend entries
        title_width = len(legend.title) * 10 if legend.title else 100
        
        # Calculate width based on longest description
        max_desc_width = 0
        for desc in legend.color_entries.values():
            if desc:
                max_desc_width = max(max_desc_width, len(desc) * 8)
        
        # Add space for color swatch + padding
        swatch_width = 30
        padding = 20
        
        base_width = max(title_width, max_desc_width + swatch_width + padding, 250)
        base_height = max(120, 60 + len(legend.color_entries) * 30)
        
        card_width = base_width * zoom
        card_height = base_height * zoom
        
        half_width = card_width // 2
        half_height = card_height // 2
        
        # Create shadow effect
        shadow_offset = int(3 * zoom)
        for i in range(3, 0, -1):
            shadow_color = '#e0e0e0' if i == 3 else ('#d0d0d0' if i == 2 else '#c0c0c0')
            shadow = self.app.canvas.create_rectangle(
                x - half_width + i, y - half_height + i,
                x + half_width + i, y + half_height + i,
                fill=shadow_color, outline='', width=0,
                tags=(f"legend_{legend_id}", "legend", "shadow")
            )
            group.append(shadow)

        # Main card (no color outline - legend cards are neutral)
        main_card = self.app.canvas.create_rectangle(
            x - half_width, y - half_height, x + half_width, y + half_height,
            fill=COLORS['surface'], outline=COLORS['border'], width=2,
            tags=(f"legend_{legend_id}", "legend")
        )
        group.append(main_card)
        
        # Header
        header_height = int(35 * zoom)
        header = self.app.canvas.create_rectangle(
            x - half_width, y - half_height, x + half_width, y - half_height + header_height,
            fill=COLORS['slate_gray'], outline='', width=0,
            tags=(f"legend_{legend_id}", "legend")
        )
        group.append(header)
        
        # Icon and title in header
        icon_x = x - half_width + int(15 * zoom)
        icon_y = y - half_height + int(17 * zoom)
        
        # Title text (no folder icon)
        title_text = self.app.canvas.create_text(
            icon_x, icon_y,
            text=legend.title or "Legend",
            anchor="w", font=("Segoe UI", int(12 * zoom), "bold"), 
            fill='white',
            tags=(f"legend_{legend_id}", "legend")
        )
        self.store_text_font_size(title_text, ("Segoe UI", 12, "bold"))
        group.append(title_text)

        # Color entries
        if legend.color_entries:
            entry_start_y = y - half_height + header_height + int(15 * zoom)
            entry_x = x - half_width + int(15 * zoom)
            
            line_height = int(25 * zoom)
            swatch_size = int(15 * zoom)
            
            for i, (color_index, description) in enumerate(legend.color_entries.items()):
                entry_y = entry_start_y + (i * line_height)
                
                # Draw color swatch
                if isinstance(color_index, (int, str)):
                    try:
                        color_idx = int(color_index)
                        color = CARD_COLORS[color_idx % len(CARD_COLORS)]
                    except (ValueError, IndexError):
                        color = CARD_COLORS[0]
                else:
                    color = CARD_COLORS[0]
                
                swatch = self.app.canvas.create_rectangle(
                    entry_x, entry_y - swatch_size//2,
                    entry_x + swatch_size, entry_y + swatch_size//2,
                    fill=color, outline=COLORS['border'], width=1,
                    tags=(f"legend_{legend_id}", "legend")
                )
                group.append(swatch)
                
                # Draw description text
                desc_text = self.app.canvas.create_text(
                    entry_x + swatch_size + int(10 * zoom), entry_y, 
                    text=description or f"Color {color_index}",
                    anchor="w", font=("Segoe UI", int(10 * zoom)),
                    fill=COLORS['text_primary'], 
                    tags=(f"legend_{legend_id}", "legend")
                )
                self.store_text_font_size(desc_text, ("Segoe UI", 10))
                group.append(desc_text)

        self.app.legend_widgets[legend_id] = group
        
        # Add event bindings
        for item in group:
            self.app.canvas.tag_bind(item, "<Double-Button-1>", 
                                   lambda e, lid=legend_id: self.app.events.edit_legend(lid))
        
        self.add_legend_hover_effects(legend_id, group)
        logger.info(f"Widget creation complete for legend {legend_id}")

    def add_legend_hover_effects(self, legend_id, group):
        """Add hover effects to legend widgets"""
        def on_enter(event):
            if self.app.events.connecting and self.app.events.connection_start == legend_id:
                return
            for item in group:
                if 'shadow' not in self.app.canvas.gettags(item):
                    if self.app.canvas.type(item) == 'rectangle':
                        self.app.canvas.itemconfig(item, outline=COLORS['primary'], width=3)
        
        def on_leave(event):
            if self.app.events.connecting and self.app.events.connection_start == legend_id:
                return
            for item in group:
                if 'shadow' not in self.app.canvas.gettags(item):
                    if self.app.canvas.type(item) == 'rectangle':
                        # Restore original border
                        if self.app.canvas.itemcget(item, 'fill') == COLORS['slate_gray']:
                            # Header - no outline
                            self.app.canvas.itemconfig(item, outline='', width=0)
                        else:
                            # Main card - restore border
                            self.app.canvas.itemconfig(item, outline=COLORS['border'], width=2)
        
        for item in group:
            self.app.canvas.tag_bind(item, "<Enter>", on_enter)
            self.app.canvas.tag_bind(item, "<Leave>", on_leave)

    def highlight_legend_for_connection(self, legend_id):
        """Highlight a legend for connection"""
        group = self.app.legend_widgets.get(legend_id, [])
        
        for item in group:
            tags = self.app.canvas.gettags(item)
            if 'shadow' in tags:
                continue
            
            item_type = self.app.canvas.type(item)
            if item_type == 'rectangle':
                # Header
                if self.app.canvas.itemcget(item, 'fill') == COLORS['slate_gray']:
                     self.app.canvas.itemconfig(item, fill=COLORS['accent'])
                # Main card
                else:
                     self.app.canvas.itemconfig(item, fill=COLORS['surface_bright'])

    def unhighlight_legend_for_connection(self, legend_id):
        """Unhighlight a legend for connection"""
        group = self.app.legend_widgets.get(legend_id, [])

        for item in group:
            tags = self.app.canvas.gettags(item)
            if 'shadow' in tags:
                continue

            item_type = self.app.canvas.type(item)
            if item_type == 'rectangle':
                # Header
                if self.app.canvas.itemcget(item, 'fill') == COLORS['accent']:
                    self.app.canvas.itemconfig(item, fill=COLORS['slate_gray'])
                # Main card
                else:
                    self.app.canvas.itemconfig(item, fill=COLORS['surface'])