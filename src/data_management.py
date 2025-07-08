# This file will contain data management logic.
import tkinter as tk
from tkinter import messagebox, filedialog
import csv
import os
import json
import zipfile
import tempfile
import shutil
import logging
import threading
import urllib.request
import urllib.error
import webbrowser

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from src.models import Person, TextboxCard, LegendCard
from src.dialogs import VersionUpdateDialog, NoUpdateDialog
from src.constants import COLORS, CARD_COLORS, COMRADE_VERSION

logger = logging.getLogger(__name__)

class DataManagement:
    def __init__(self, app):
        self.app = app

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
                    writer.writerow(['ID', 'Name', 'DOB', 'Alias', 'Address', 'Phone', 'X', 'Y', 'Color', 'Files', 'Type'])
                    
                    # Save people
                    for person_id, person in self.app.people.items():
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
                            person.color, files_json, 'person'
                        ])
                    
                    # Save textboxes
                    for textbox_id, textbox in self.app.textboxes.items():
                        writer.writerow([
                            textbox_id, textbox.title, textbox.content, '', 
                            '', '', textbox.x, textbox.y, 
                            textbox.color, '', 'textbox'
                        ])
                    
                    # Save legend cards
                    for legend_id, legend in self.app.legends.items():
                        # Convert color_entries dict to JSON string for CSV storage
                        color_entries_json = json.dumps(legend.color_entries) if legend.color_entries else ""
                        writer.writerow([
                            legend_id, legend.title, color_entries_json, '', 
                            '', '', legend.x, legend.y, 
                            0, '', 'legend'  # legends don't have a color property
                        ])
                    
                    writer.writerow(['CONNECTIONS'])
                    writer.writerow(['From_ID', 'To_ID', 'Label'])
                    
                    # Save connections
                    saved = set()
                    # Save connections from people
                    for id1, person in self.app.people.items():
                        for id2, label in person.connections.items():
                            key = (min(id1, id2), max(id1, id2))
                            if key not in saved:
                                writer.writerow([id1, id2, label])
                                saved.add(key)
                    
                    # Save connections from textboxes
                    for id1, textbox in self.app.textboxes.items():
                        for id2, label in textbox.connections.items():
                            key = (min(id1, id2), max(id1, id2))
                            if key not in saved:
                                writer.writerow([id1, id2, label])
                                saved.add(key)
                    
                    # Save connections from legend cards
                    for id1, legend in self.app.legends.items():
                        for id2, label in legend.connections.items():
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
        
        # Reset zoom to default before loading to prevent positioning issues
        if hasattr(self.app, 'zoom_var') and self.app.zoom_var.get() != 1.0:
            self.app.zoom_var.set(1.0)
            # Actually trigger the zoom event handler to apply the zoom
            self.app.events.on_zoom(1.0)
            self.app.update_status("Zoom reset for loading", duration=2000)

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
                                # Check if IDs exist in people, textboxes, or legends
                                card1 = self.app.people.get(id1) or self.app.textboxes.get(id1) or self.app.legends.get(id1)
                                card2 = self.app.people.get(id2) or self.app.textboxes.get(id2) or self.app.legends.get(id2)
                                
                                if card1 and card2:
                                    card1.connections[id2] = label
                                    card2.connections[id1] = label
                                else:
                                    logger.warning(f"Connection references missing card: {id1} or {id2}")
                        else:
                            if len(row) >= 8:
                                card_id = int(row[0])
                                
                                # Check if this is a textbox or legend (new format with Type column)
                                is_textbox = False
                                is_legend = False
                                if len(row) >= 11:
                                    if row[10] == 'textbox':
                                        is_textbox = True
                                    elif row[10] == 'legend':
                                        is_legend = True
                                elif len(row) >= 3 and not row[2]:  # Empty DOB might indicate textbox in old format
                                    # Additional heuristic: if name is actually content (longer than typical name)
                                    if len(row[1]) > 50:
                                        is_textbox = True
                                
                                if is_legend:
                                    # This is a legend card
                                    color_entries = {}
                                    if len(row) > 2 and row[2]:  # color_entries JSON is in the content field
                                        try:
                                            color_entries = json.loads(row[2])
                                        except json.JSONDecodeError:
                                            logger.warning(f"Invalid color_entries data for legend {card_id}")
                                    
                                    legend = LegendCard(row[1], color_entries)
                                    legend.x = float(row[6])
                                    legend.y = float(row[7])
                                    
                                    self.app.legends[card_id] = legend
                                    self.app.next_id = max(self.app.next_id, card_id + 1)
                                elif is_textbox:
                                    # This is a textbox card
                                    textbox = TextboxCard(row[1], row[2] if len(row) > 2 else '')
                                    textbox.x = float(row[6])
                                    textbox.y = float(row[7])
                                    
                                    # Handle color field
                                    if len(row) >= 9:
                                        textbox.color = int(row[8])
                                    else:
                                        textbox.color = 0
                                    
                                    self.app.textboxes[card_id] = textbox
                                    self.app.next_id = max(self.app.next_id, card_id + 1)
                                else:
                                    # This is a person card
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
                                            logger.warning(f"Invalid files data for person {card_id}")
                                            person.files = []
                                    else:
                                        person.files = []
                                    
                                    self.app.people[card_id] = person
                                    self.app.next_id = max(self.app.next_id, card_id + 1)
                
                # Create widgets at base zoom (1.0)
                for person_id in self.app.people:
                    self.app.canvas_helpers.create_person_widget(person_id, zoom=1.0)
                
                for textbox_id in self.app.textboxes:
                    self.app.canvas_helpers.create_textbox_widget(textbox_id, zoom=1.0)
                
                for legend_id in self.app.legends:
                    self.app.canvas_helpers.create_legend_widget(legend_id, zoom=1.0)
                
                # Draw connections for the base zoom
                self.app.canvas_helpers.update_connections()

                # Then apply current zoom if different from 1.0
                if hasattr(self.app.events, 'last_zoom') and self.app.events.last_zoom != 1.0:
                    self.app.events.on_zoom(self.app.events.last_zoom)
                
                # Count extracted files
                total_files = sum(len(person.files) for person in self.app.people.values())
                messagebox.showinfo("Success", f"Data loaded successfully!\n\nLoaded:\n• {len(self.app.people)} people\n• {len(self.app.textboxes)} textbox cards\n• {len(self.app.legends)} legend cards\n• {total_files} attached files\n\nFiles extracted to: {files_dir}")
    
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
                        if id1 in self.app.people and id2 in self.app.people:
                            self.app.people[id1].connections[id2] = label
                            self.app.people[id2].connections[id1] = label
                        else:
                            logger.warning(f"Connection references missing person: {id1} or {id2}")
                else:
                    if len(row) >= 8:
                        person_id = int(row[0])
                        person = Person(row[1], row[2], row[3], row[4, row[5]])
                        person.x = float(row[6])
                        person.y = float(row[7])
                        
                        # Handle color field for backward compatibility
                        if len(row) >= 9:
                            person.color = int(row[8])
                        else:
                            person.color = 0
                            
                        # No files in legacy format
                        person.files = []
                        
                        self.app.people[person_id] = person
                        self.app.next_id = max(self.app.next_id, person_id + 1)
            
            for person_id in self.app.people:
                self.app.canvas_helpers.create_person_widget(person_id)
            self.app.canvas_helpers.update_connections()
            messagebox.showinfo("Success", "Legacy CSV data loaded successfully!\n\nNote: Use the new ZIP format for file attachments.")

    def export_to_png(self):
        """Export the current network diagram to PNG format at high DPI
        
        This function exports the complete network visualization including:
        - All person cards with their information
        - All textbox cards with their content
        - Connection lines and labels between all card types
        - Attached images for people (if any)
        - High DPI quality for crisp output
        """
        if not PIL_AVAILABLE:
            messagebox.showerror("Error", "PIL (Pillow) library is not installed.\n\nTo use PNG export, please install it with:\npip install Pillow")
            return
            
        if not self.app.people and not self.app.textboxes and not self.app.legends:
            messagebox.showwarning("Warning", "No people, textboxes, or legends to export. Please add some content first.")
            return
        
        # Store current zoom level to restore later
        original_zoom = self.app.zoom_var.get() if hasattr(self.app, 'zoom_var') else 1.0
        
        # Reset zoom to zoomed out view before exporting to capture more of the network
        if hasattr(self.app, 'zoom_var') and self.app.zoom_var.get() != 0.5:
            self.app.zoom_var.set(0.5)
            # Actually trigger the zoom event handler to apply the zoom
            self.app.events.on_zoom(0.5)
            self.app.update_status("Zoom reset for export", duration=2000)
            
        filename = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            title="Export Network as PNG (High DPI)"
        )
        
        if not filename:
            # Restore original zoom level if user cancels
            if hasattr(self.app, 'zoom_var'):
                self.app.zoom_var.set(original_zoom)
                # Actually trigger the zoom event handler to apply the zoom
                self.app.events.on_zoom(original_zoom)
            return
            
        try:            # High DPI settings for crisp output
            dpi_scale = 6.0  # 6x scaling for high DPI (600 DPI equivalent)
            target_dpi = 600  # Target DPI for print quality
            
            # Use the fixed canvas dimensions scaled up for high DPI
            base_width = self.app.fixed_canvas_width
            base_height = self.app.fixed_canvas_height
            canvas_width = int(base_width * dpi_scale)
            canvas_height = int(base_height * dpi_scale)
            
            # Create a white background image at high resolution
            image = Image.new('RGB', (canvas_width, canvas_height), '#f8fafc')
            draw = ImageDraw.Draw(image)
            
            # Get current zoom level and apply DPI scaling
            base_zoom = self.app.events.last_zoom
            zoom = base_zoom * dpi_scale
              # Draw grid pattern (scaled for high DPI)
            grid_size = int(40 * dpi_scale)
            grid_color = '#e2e8f0'
            grid_width = max(1, int(1 * dpi_scale))
            for x in range(0, canvas_width, grid_size):
                draw.line([(x, 0), (x, canvas_height)], fill=grid_color, width=grid_width)
            for y in range(0, canvas_height, grid_size):
                draw.line([(0, y), (canvas_width, y)], fill=grid_color, width=grid_width)
            
            # Store connection data to draw labels later
            connection_labels_to_draw = []

            # Draw connections first (so they appear behind cards)
            # Handle all types of connections: person-person, person-textbox, textbox-textbox, legend-legend, etc.
            for (id1, id2) in self.app.connection_lines.keys():
                # Get the connection objects (could be person, textbox, or legend)
                card1 = self.app.people.get(id1) or self.app.textboxes.get(id1) or self.app.legends.get(id1)
                card2 = self.app.people.get(id2) or self.app.textboxes.get(id2) or self.app.legends.get(id2)
                
                if card1 and card2:
                    # Get the connection label from either card
                    label = card1.connections.get(id2, "") or card2.connections.get(id1, "")
                    
                    x1, y1 = int(card1.x * zoom), int(card1.y * zoom)
                    x2, y2 = int(card2.x * zoom), int(card2.y * zoom)
                    
                    # Draw connection line with DPI scaling
                    line_width = max(1, int(2 * dpi_scale))
                    draw.line([(x1, y1), (x2, y2)], fill=COLORS['primary'], width=line_width)
                    
                    # Store info for drawing label later
                    if label and label.strip():
                        connection_labels_to_draw.append({'label': label, 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})

            # Draw people cards
            for person_id, person in self.app.people.items():
                x = int(person.x * zoom)
                y = int(person.y * zoom)

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
                
                # Prepare details, filtering out empty values
                details = [
                    ("DOB:", person.dob),
                    ("Alias:", person.alias),
                    ("Addr:", person.address),
                    ("Phone:", person.phone)
                ]
                details = [(label, value) for label, value in details if value and value.strip()]

                # Calculate maximum width needed for details text
                max_details_width = 0
                if detail_font:
                    label_column_width = 0
                    value_column_width = 0
                    for label, value in details:
                        label_bbox = draw.textbbox((0, 0), label, font=detail_font)
                        value_bbox = draw.textbbox((0, 0), value, font=detail_font)
                        label_column_width = max(label_column_width, label_bbox[2] - label_bbox[0])
                        value_column_width = max(value_column_width, value_bbox[2] - value_bbox[0])
                    
                    column_gap = int(10 * dpi_scale)
                    max_details_width = label_column_width + column_gap + value_column_width
                else: # Fallback if font is not available
                    if details:
                        max_len = max(len(l) + len(v) for l,v in details)
                        max_details_width = max_len * int(6 * dpi_scale)

                # Calculate width needed for the header (avatar + name)
                avatar_space = int(40 * zoom) # Avatar size + padding
                name_width = 0
                if name_font:
                    name_bbox = draw.textbbox((0, 0), person.name or "Unnamed", font=name_font)
                    name_width = name_bbox[2] - name_bbox[0]
                else: # Fallback
                    name_width = len(person.name or "Unnamed") * int(7 * dpi_scale)
                
                header_width = avatar_space + name_width

                # Determine card width
                padding = int(15 * dpi_scale)
                content_width = max(header_width, max_details_width)
                
                # Check for image to include in width calculation
                image_file = None
                image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
                if hasattr(person, 'files') and person.files:
                    for file_path in person.files:
                        if os.path.exists(file_path) and os.path.splitext(file_path.lower())[1] in image_extensions:
                            image_file = file_path
                            break
                
                image_width = int(120 * dpi_scale) if image_file else 0
                image_padding = int(10 * dpi_scale) if image_file else 0

                card_width = content_width + image_width + image_padding + 2 * padding
                
                # Determine card height
                header_height = int(40 * zoom)
                line_height = int(20 * zoom)
                details_height = len(details) * line_height
                vertical_padding = int(15 * zoom)
                
                base_card_height = header_height + details_height + 2 * vertical_padding
                min_height = int(120 * zoom)
                if image_file:
                    min_height = int(140 * zoom) # Taller min height if image exists
                
                card_height = max(base_card_height, min_height)

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
                
                # Draw name in header
                name_x = avatar_x + avatar_size//2 + int(5 * zoom)
                draw.text((name_x, avatar_y - int(6 * zoom)), 
                         person.name or "Unnamed", fill='white', font=name_font)

                # Draw details
                details_start_y = y - half_height + header_height + vertical_padding
                current_y = details_start_y
                
                # Recalculate label column width for drawing
                label_column_width = 0
                if detail_font and details:
                    for label, value in details:
                        label_bbox = draw.textbbox((0, 0), label, font=detail_font)
                        label_column_width = max(label_column_width, label_bbox[2] - label_bbox[0])
                
                for label, value in details:
                    label_x = x - half_width + padding
                    data_x = label_x + label_column_width + column_gap
                    
                    # Draw label and data in separate columns
                    draw.text((label_x, current_y), label, 
                            fill=COLORS['text_primary'], font=detail_font)
                    draw.text((data_x, current_y), value, 
                            fill=COLORS['text_primary'], font=detail_font)
                    current_y += line_height
                
                # Draw attached image if available
                if image_file:
                    try:
                        # Load and resize image for export
                        person_image = Image.open(image_file)
                        
                        # Calculate image dimensions (maintain aspect ratio)
                        max_img_height = card_height - header_height - (2 * vertical_padding)
                        max_img_width = image_width
                        
                        person_image.thumbnail((max_img_width, max_img_height), Image.Resampling.LANCZOS)
                        img_width, img_height = person_image.size
                        
                        # Position image on the right side of the card
                        img_x = x + half_width - padding - (max_img_width // 2)
                        img_y = y - half_height + header_height + vertical_padding + (max_img_height // 2)
                        
                        # Paste the image onto the main image
                        image.paste(person_image, (img_x - img_width//2, img_y - img_height//2), person_image if person_image.mode == 'RGBA' else None)
                        
                    except Exception as e:
                        logger.error(f"Failed to include image {image_file} in PNG export: {e}")

            # Draw textbox cards
            for textbox_id, textbox in self.app.textboxes.items():
                x = int(textbox.x * zoom)
                y = int(textbox.y * zoom)

                # Try to load fonts for textbox with DPI scaling
                title_font_size = int(12 * dpi_scale)
                content_font_size = int(10 * dpi_scale)
                try:
                    title_font = ImageFont.truetype("arial.ttf", title_font_size)
                    content_font = ImageFont.truetype("arial.ttf", content_font_size)
                except:
                    try:
                        title_font = ImageFont.load_default()
                        content_font = ImageFont.load_default()
                    except:
                        title_font = None
                        content_font = None

                # Calculate textbox dimensions with text wrapping
                # Calculate title width using actual font if available
                title_width = 0
                if title_font and textbox.title:
                    title_bbox = draw.textbbox((0, 0), textbox.title, font=title_font)
                    title_width = title_bbox[2] - title_bbox[0]
                else:
                    title_width = len(textbox.title) * int(10 * dpi_scale) if textbox.title else int(100 * dpi_scale)
                
                # For content, we'll use a fixed width for wrapping and calculate height based on wrapped lines
                content_char_width = 70  # Characters per line for export (higher than canvas for better readability)
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
                
                # Calculate dimensions with DPI scaling like person cards
                # Calculate actual content width based on wrapped lines
                content_width = 0
                if content_font and wrapped_lines:
                    for line in wrapped_lines:
                        if line.strip():
                            line_bbox = draw.textbbox((0, 0), line, font=content_font)
                            line_width = line_bbox[2] - line_bbox[0]
                            content_width = max(content_width, line_width)
                else:
                    # Fallback calculation if font is not available
                    if wrapped_lines:
                        max_line_length = max(len(line) for line in wrapped_lines if line.strip())
                        content_width = max_line_length * int(6 * dpi_scale)
                
                padding = int(15 * dpi_scale)
                base_width = max(title_width, content_width, int(250 * dpi_scale))
                
                # Calculate height based on content lines with DPI scaling
                header_height = int(45 * zoom)
                line_height = int(18 * zoom)
                content_height = len(wrapped_lines) * line_height
                vertical_padding = int(15 * zoom)
                
                base_card_height = header_height + content_height + 2 * vertical_padding
                min_height = int(120 * zoom)
                base_height = max(base_card_height, min_height)
                
                card_width = base_width + 2 * padding
                card_height = base_height
                
                half_width = card_width // 2
                half_height = card_height // 2

                # Draw textbox shadow with DPI scaling
                shadow_offset = int(3 * dpi_scale)
                for i in range(3, 0, -1):
                    shadow_color = '#e0e0e0' if i == 3 else ('#d0d0d0' if i == 2 else '#c0c0c0')
                    offset = int(i * dpi_scale)
                    draw.rectangle([
                        x - half_width + offset, y - half_height + offset,
                        x + half_width + offset, y + half_height + offset
                    ], fill=shadow_color)

                # Get textbox's color for consistency with canvas display
                textbox_color = CARD_COLORS[textbox.color % len(CARD_COLORS)]
                
                # Draw main textbox card with DPI scaling
                card_border_width = max(1, int(2 * dpi_scale))
                draw.rectangle([
                    x - half_width, y - half_height,
                    x + half_width, y + half_height
                ], fill=COLORS['surface'], outline=textbox_color, width=card_border_width)
                
                # Draw header
                header_height = int(45 * zoom)
                draw.rectangle([
                    x - half_width, y - half_height,
                    x + half_width, y - half_height + header_height
                ], fill=textbox_color)

                # Draw title in header
                title_x = x - half_width + int(15 * zoom)
                title_y = y - half_height + int(17 * zoom)
                
                # Draw square icon (similar to person's circular avatar)
                icon_size = int(16 * zoom)
                square_border_width = max(1, int(2 * dpi_scale))
                
                draw.rectangle([
                    title_x - icon_size//2, title_y - icon_size//2,
                    title_x + icon_size//2, title_y + icon_size//2
                ], fill='white', outline=textbox_color, width=square_border_width)
                
                # Draw title text
                text_x = title_x + icon_size//2 + int(5 * zoom)
                draw.text((text_x, title_y - int(6 * zoom)), 
                        textbox.title or "Untitled", fill='white', font=title_font or None)

                # Draw content
                if textbox.content:
                    content_start_y = y - half_height + header_height + int(15 * zoom)
                    content_x = x - half_width + int(15 * zoom)
                    
                    # Use wrapped lines for display (limit to 8 lines for export)
                    display_lines = wrapped_lines[:8]
                    line_height = int(18 * zoom)
                    
                    for i, line in enumerate(display_lines):
                        if line.strip():  # Only show non-empty lines
                            line_y = content_start_y + (i * line_height)
                            
                            if content_font:
                                draw.text((content_x, line_y), line, 
                                        fill=COLORS['text_primary'], font=content_font)
                            else:
                                draw.text((content_x, line_y), line, 
                                        fill=COLORS['text_primary'])
                    
                    # Show "..." if there are more lines
                    if len(wrapped_lines) > 8:
                        more_y = content_start_y + (8 * line_height)
                        if content_font:
                            draw.text((content_x, more_y), "...", 
                                    fill=COLORS['text_secondary'], font=content_font)
                        else:
                            draw.text((content_x, more_y), "...", 
                                    fill=COLORS['text_secondary'])

            # Draw legend cards
            for legend_id, legend in self.app.legends.items():
                x = int(legend.x * zoom)
                y = int(legend.y * zoom)

                # Try to load fonts for legend with DPI scaling
                title_font_size = int(12 * dpi_scale)
                entry_font_size = int(10 * dpi_scale)
                try:
                    title_font = ImageFont.truetype("arial.ttf", title_font_size)
                    entry_font = ImageFont.truetype("arial.ttf", entry_font_size)
                except:
                    try:
                        title_font = ImageFont.load_default()
                        entry_font = ImageFont.load_default()
                    except:
                        title_font = None
                        entry_font = None

                # Calculate legend dimensions
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
                
                card_width = int(base_width * zoom)
                card_height = int(base_height * zoom)
                
                half_width = card_width // 2
                half_height = card_height // 2

                # Draw legend shadow with DPI scaling
                shadow_offset = int(3 * dpi_scale)
                for i in range(3, 0, -1):
                    shadow_color = '#e0e0e0' if i == 3 else ('#d0d0d0' if i == 2 else '#c0c0c0')
                    offset = int(i * dpi_scale)
                    draw.rectangle([
                        x - half_width + offset, y - half_height + offset,
                        x + half_width + offset, y + half_height + offset
                    ], fill=shadow_color)

                # Draw main legend card with DPI scaling
                card_border_width = max(1, int(2 * dpi_scale))
                draw.rectangle([
                    x - half_width, y - half_height,
                    x + half_width, y + half_height
                ], fill=COLORS['surface'], outline=COLORS['border'], width=card_border_width)
                
                # Draw header
                header_height = int(45 * zoom)
                draw.rectangle([
                    x - half_width, y - half_height,
                    x + half_width, y - half_height + header_height
                ], fill=COLORS['slate_gray'])

                # Draw title in header (no folder icon)
                title_x = x - half_width + int(15 * zoom)
                title_y = y - half_height + int(17 * zoom)
                
                # Draw title text
                draw.text((title_x, title_y - int(6 * zoom)), 
                        legend.title or "Legend", fill='white', font=title_font or None)

                # Draw color entries
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
                        
                        swatch_border_width = max(1, int(1 * dpi_scale))
                        draw.rectangle([
                            entry_x, entry_y - swatch_size//2,
                            entry_x + swatch_size, entry_y + swatch_size//2
                        ], fill=color, outline=COLORS['border'], width=swatch_border_width)
                        
                        # Draw description text
                        desc_x = entry_x + swatch_size + int(10 * zoom)
                        if entry_font:
                            draw.text((desc_x, entry_y - int(5 * zoom)), 
                                    description or f"Color {color_index}",
                                    fill=COLORS['text_primary'], font=entry_font)
                        else:
                            draw.text((desc_x, entry_y - int(5 * zoom)), 
                                    description or f"Color {color_index}",
                                    fill=COLORS['text_primary'])

            # Draw connection labels on top of cards
            for conn in connection_labels_to_draw:
                mid_x = (conn['x1'] + conn['x2']) // 2
                mid_y = (conn['y1'] + conn['y2']) // 2
                label = conn['label']
                
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

            # Save the image with high DPI information
            image.save(filename, 'PNG', dpi=(target_dpi, target_dpi))
            messagebox.showinfo("Success", f"High DPI network exported successfully to:\n{filename}\n\nResolution: {canvas_width}x{canvas_height} pixels\nDPI: {target_dpi}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export PNG:\n{str(e)}")
        finally:
            # Restore original zoom level
            if hasattr(self.app, 'zoom_var'):
                self.app.zoom_var.set(original_zoom)
                # Actually trigger the zoom event handler to apply the zoom
                self.app.events.on_zoom(original_zoom)

    def clear_all(self):
        # Check if there's any data to clear
        total_people = len(self.app.people)
        total_textboxes = len(self.app.textboxes)
        total_legends = len(self.app.legends)
        total_connections = sum(len(person.connections) for person in self.app.people.values()) // 2
        total_textbox_connections = sum(len(textbox.connections) for textbox in self.app.textboxes.values()) // 2
        total_legend_connections = sum(len(legend.connections) for legend in self.app.legends.values()) // 2
        
        if not total_people and not total_textboxes and not total_legends:
            messagebox.showinfo("Nothing to Clear", "There are no people, textboxes, legends, or connections to clear.")
            return
            
        # Build confirmation message
        items_to_delete = []
        if total_people > 0:
            items_to_delete.append(f"• {total_people} people")
        if total_textboxes > 0:
            items_to_delete.append(f"• {total_textboxes} textbox cards")
        if total_legends > 0:
            items_to_delete.append(f"• {total_legends} legend cards")
        if total_connections > 0 or total_textbox_connections > 0 or total_legend_connections > 0:
            total_all_connections = total_connections + total_textbox_connections + total_legend_connections
            items_to_delete.append(f"• {total_all_connections} connections")
            
        result = messagebox.askyesno(
            "Confirm Clear All", 
            f"Are you sure you want to clear all data?\n\n"
            f"This will permanently delete:\n"
            f"{chr(10).join(items_to_delete)}\n\n"
            f"This action cannot be undone!",
            icon='warning'
        )
        
        if not result:
            return
            
        # Proceed with clearing
        self.app.canvas.delete("all")
        self.app.people.clear()
        self.app.person_widgets.clear()
        self.app.textboxes.clear()
        self.app.textbox_widgets.clear()
        self.app.legends.clear()
        self.app.legend_widgets.clear()
        self.app.connection_lines.clear()
        self.app.original_font_sizes.clear()
        self.app.original_image_sizes.clear()
        self.app.image_cache.clear()
        self.app.scaled_image_cache.clear()
        self.app.base_image_cache.clear()
        self.app.selected_person = None
        self.app.selected_textbox = None
        self.app.selected_legend = None
        self.app.selected_connection = None
        self.app.next_id = 1
        
        # Reset zoom and view
        if hasattr(self.app, 'events'):
            self.app.events.last_zoom = 1.0
            self.app.canvas.xview_moveto(0)
            self.app.canvas.yview_moveto(0)

        # Recreate the grid pattern after clearing
        self.app.canvas_helpers.add_grid_pattern()
        
        # Update status
        self.app.update_status("All data cleared successfully")

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

    def check_for_updates(self, silent=False):
        """Check for updates from GitHub releases"""
        logger.info(f"Checking for updates (silent={silent})...")
        
        # Update status using root.after to ensure it's on the main thread
        if not silent:
            self.app.root.after(0, lambda: self.app.update_status("🔄 Checking for updates..."))
        
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
                    self.app.root.after(0, lambda: self.handle_version_check_result(latest_tag, release_url, silent))
                    
            except urllib.error.URLError as e:
                logger.error(f"Network error checking for updates: {e}")
                if not silent:
                    self.app.root.after(0, lambda: self.handle_version_check_error("Network error"))
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error checking for updates: {e}")
                if not silent:
                    self.app.root.after(0, lambda: self.handle_version_check_error("Data parsing error"))
            except Exception as e:
                logger.error(f"Unexpected error checking for updates: {e}")
                if not silent:
                    self.app.root.after(0, lambda: self.handle_version_check_error("Unexpected error"))
        
        # Start the check in a background thread
        try:
            thread = threading.Thread(target=check_updates_thread, daemon=True)
            thread.start()
            logger.info("Background update check thread started successfully")
        except Exception as e:
            logger.error(f"Failed to start update check thread: {e}")
            if not silent:
                self.app.root.after(0, lambda: self.handle_version_check_error("Failed to start update check"))
    
    def handle_version_check_result(self, latest_tag, release_url, silent):
        if latest_tag and release_url:
            if self.is_newer_version(COMRADE_VERSION, latest_tag):
                VersionUpdateDialog(self.app.root, latest_tag, release_url)
            elif not silent:
                NoUpdateDialog(self.app.root, COMRADE_VERSION)
        elif not silent:
            self.app.update_status("❌ Unable to check for updates.")

    def handle_version_check_error(self, error_type):
        """Handle version check errors on the main thread"""
        logger.error(f"Version check failed: {error_type}")
        self.app.update_status(f"❌ Update check failed: {error_type}")
        messagebox.showerror(
            "Update Check Failed",
            f"Failed to check for updates: {error_type}\n\n"
            "Please check your internet connection and try again.\n"
            "You can also visit https://github.com/BitEU/COMRADE/releases manually.",
            parent=self.app.root
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
                    self.app.root.after(0, lambda: self.handle_silent_version_check_result(latest_tag, release_url))
                    
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
            dialog = VersionUpdateDialog(self.app.root, current_version, latest_version, release_url)
            self.app.root.wait_window(dialog.dialog)
        else:
            logger.info("Already up to date - no dialog shown")
