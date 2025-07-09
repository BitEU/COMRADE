from datetime import datetime
from src.constants import COLORS, CARD_COLORS
from src.dialogs import ConnectionLabelDialog, PersonDialog, TextboxDialog, LegendDialog
from tkinter import messagebox

# This file will contain event handling logic.

class EventHandlers:
    def __init__(self, app):
        self.app = app
        self.dragging = False
        self.drag_data = {"x": 0, "y": 0}
        self.connecting = False
        self.connection_start = None
        self.temp_line = None
        self.selected_person = None
        self.selected_textbox = None
        self.selected_legend = None
        self.selected_connection = None
        self.last_zoom = 1.0
        self.zoom_debounce_timer = None
        self._panning = False
        self.current_hover = None
        self._last_mouse_move_time = 0
        self._pending_color_refresh = None

    def on_zoom(self, value):
        # Scale the canvas content based on the zoom value
        try:
            zoom = float(value)
        except ValueError:
            zoom = 1.0
        
        # Avoid unnecessary work if zoom hasn't changed significantly
        if abs(zoom - self.last_zoom) < 0.01:
            return
        
        # Store previous zoom for efficient scaling
        prev_zoom = self.last_zoom
        
        # Use single canvas.scale operation for better performance
        scale_factor = zoom / prev_zoom
        self.app.canvas.scale("all", 0, 0, scale_factor, scale_factor)
        self.last_zoom = zoom
        
        # Keep the scroll region fixed to maintain consistent canvas size
        self.app.canvas.configure(scrollregion=(0, 0, self.app.fixed_canvas_width, self.app.fixed_canvas_height))
        
        # Batch UI updates for better performance
        self.debounced_zoom_update(zoom)

    def debounced_zoom_update(self, zoom):
        """Perform expensive zoom operations with debouncing"""
        # Cancel previous timer if it exists
        if self.zoom_debounce_timer:
            self.app.root.after_cancel(self.zoom_debounce_timer)
        
        # Schedule the expensive operations after a short delay
        self.zoom_debounce_timer = self.app.root.after(50, lambda: self._perform_zoom_update(zoom))
    
    def _perform_zoom_update(self, zoom):
        """Perform the actual expensive zoom update operations"""
        self.app.canvas_helpers.rescale_text(zoom)
        self.app.canvas_helpers.rescale_images(zoom)
        self.app.canvas_helpers.update_connections()
        self.app.canvas_helpers.redraw_grid()
        self.zoom_debounce_timer = None

    def on_canvas_resize(self, event):
        self.app.canvas_helpers.redraw_grid()

    def on_canvas_click(self, event):
        # Account for zoom in hit detection
        zoom = self.last_zoom
        # Make tolerance proportional to zoom level
        tolerance = max(3, int(10 * (1/zoom))) # Increase tolerance as we zoom out
        
        # Convert screen coordinates to canvas coordinates to handle scrolled content
        canvas_x = self.app.canvas.canvasx(event.x)
        canvas_y = self.app.canvas.canvasy(event.y)
        
        # Use canvas coordinates for hit detection
        items = self.app.canvas.find_overlapping(canvas_x - tolerance, canvas_y - tolerance, canvas_x + tolerance, canvas_y + tolerance)
        
        # Always clear selections on a new click
        self.clear_connection_selection()
        self.selected_person = None
        self.selected_textbox = None
        self.selected_legend = None
        self.dragging = False

        if not items:
            return

        # Iterate from topmost to bottommost item
        for item in reversed(items):
            tags = self.app.canvas.gettags(item)

            # Check for connection label first
            if any(t.startswith("connection_label_") or t.startswith("connection_clickable_") for t in tags):
                for tag in tags:
                    if tag.startswith("connection_label_") or tag.startswith("connection_clickable_"):
                        parts = tag.split("_")
                        if len(parts) >= 4:
                            try:
                                id1, id2 = int(parts[2]), int(parts[3])
                                self.selected_connection = (min(id1, id2), max(id1, id2))
                                self.highlight_connection_selection()
                                self.app.canvas.focus_set()
                                return  # Exit after handling the click
                            except ValueError:
                                continue
            
            # Check for textbox
            if any("textbox" in tag for tag in tags):
                for tag in tags:
                    if tag.startswith("textbox_"):
                        textbox_id = int(tag.split("_")[1])
                        self.selected_textbox = textbox_id
                        self.drag_data = {"x": canvas_x, "y": canvas_y}
                        self.dragging = True
                        return # Exit after handling the click
            
            # Check for legend
            if any("legend" in tag for tag in tags):
                for tag in tags:
                    if tag.startswith("legend_"):
                        legend_id = int(tag.split("_")[1])
                        self.selected_legend = legend_id
                        self.drag_data = {"x": canvas_x, "y": canvas_y}
                        self.dragging = True
                        return # Exit after handling the click
            
            # If not a connection, textbox, or legend, check for a person
            if any("person" in tag for tag in tags):
                for tag in tags:
                    if tag.startswith("person_"):
                        person_id = int(tag.split("_")[1])
                        self.selected_person = person_id
                        self.drag_data = {"x": canvas_x, "y": canvas_y}
                        self.dragging = True
                        return # Exit after handling the click

    def on_canvas_drag(self, event):
        if self.dragging and (self.selected_person or self.selected_textbox or self.selected_legend):
            zoom = self.last_zoom
            
            # Convert screen coordinates to canvas coordinates
            canvas_x = self.app.canvas.canvasx(event.x)
            canvas_y = self.app.canvas.canvasy(event.y)
            
            # Calculate the movement delta in canvas coordinates
            dx_canvas = canvas_x - self.drag_data["x"]
            dy_canvas = canvas_y - self.drag_data["y"]
            
            # Convert canvas delta to world delta (compensate for zoom)
            dx_world = dx_canvas / zoom
            dy_world = dy_canvas / zoom
            
            if self.selected_person:
                # Update logical (unscaled) position using world delta
                self.app.people[self.selected_person].x += dx_world
                self.app.people[self.selected_person].y += dy_world

                # Move existing canvas items directly during drag (much more efficient)
                person_items = self.app.person_widgets[self.selected_person]
                for item in person_items:
                    self.app.canvas.move(item, dx_canvas, dy_canvas)
            
            elif self.selected_textbox:
                # Update logical (unscaled) position using world delta
                self.app.textboxes[self.selected_textbox].x += dx_world
                self.app.textboxes[self.selected_textbox].y += dy_world

                # Move existing canvas items directly during drag (much more efficient)
                textbox_items = self.app.textbox_widgets[self.selected_textbox]
                for item in textbox_items:
                    self.app.canvas.move(item, dx_canvas, dy_canvas)
            
            elif self.selected_legend:
                # Update logical (unscaled) position using world delta
                self.app.legends[self.selected_legend].x += dx_world
                self.app.legends[self.selected_legend].y += dy_world

                # Move existing canvas items directly during drag (much more efficient)
                legend_items = self.app.legend_widgets[self.selected_legend]
                for item in legend_items:
                    self.app.canvas.move(item, dx_canvas, dy_canvas)

            # Update connections immediately (but efficiently)
            self.app.canvas_helpers.update_connections()  # Update connections
            # Update drag data for next movement
            self.drag_data = {"x": canvas_x, "y": canvas_y}

    def on_canvas_release(self, event):
        if self.dragging and (self.selected_person or self.selected_textbox or self.selected_legend):
            self.dragging = False
            
            # Don't refresh the widget - it's already at the correct position and scale
            # Only refresh if there was a pending color change
            if self._pending_color_refresh:
                if self.selected_person:
                    self.app.root.after(50, lambda: self.app.refresh_person_widget(self._pending_color_refresh))
                elif self.selected_textbox:
                    self.app.root.after(50, lambda: self.app.refresh_textbox_widget(self._pending_color_refresh))
                elif self.selected_legend:
                    self.app.root.after(50, lambda: self.app.refresh_legend_widget(self._pending_color_refresh))
                self._pending_color_refresh = None
        else:
            self.dragging = False
    
    def on_double_click(self, event):
        """Handle double-click events for editing connections"""
        # Convert screen coordinates to canvas coordinates
        canvas_x = self.app.canvas.canvasx(event.x)
        canvas_y = self.app.canvas.canvasy(event.y)
        
        items = self.app.canvas.find_closest(canvas_x, canvas_y)
        if not items:
            return
             
        clicked = items[0]
        tags = self.app.canvas.gettags(clicked)
        
        # Check if double-clicked on a connection label
        for tag in tags:
            if tag.startswith("connection_label_") or tag.startswith("connection_clickable_"):
                # Extract connection IDs from tag
                parts = tag.split("_")
                if len(parts) >= 4:
                    try:
                        id1, id2 = int(parts[2]), int(parts[3])
                        self.selected_connection = (min(id1, id2), max(id1, id2))
                        self.edit_connection_label()
                        break
                    except ValueError:
                        # Not a valid connection tag, skip
                        continue
    
    def on_mouse_move(self, event):
        if self.dragging:
            return
             
        current_time = datetime.now().timestamp()
        if self._last_mouse_move_time:
            if current_time - self._last_mouse_move_time < 0.02:  # 50 FPS max
                return
        self._last_mouse_move_time = current_time
        
        tolerance = 5  # pixels
        
        canvas_x = self.app.canvas.canvasx(event.x)
        canvas_y = self.app.canvas.canvasy(event.y)
        
        items = self.app.canvas.find_overlapping(canvas_x - tolerance, canvas_y - tolerance, 
                                           canvas_x + tolerance, canvas_y + tolerance)
        
        person_id = None
        textbox_id = None
        for item in items:
            tags = self.app.canvas.gettags(item)
            if any("person" in tag for tag in tags):
                for tag in tags:
                    if tag.startswith("person_"):
                        person_id = int(tag.split("_")[1])
                        break
                if person_id is not None:
                    break
            elif any("textbox" in tag for tag in tags):
                for tag in tags:
                    if tag.startswith("textbox_"):
                        textbox_id = int(tag.split("_")[1])
                        break
                if textbox_id is not None:
                    break
        
        card_id = person_id or textbox_id
        if card_id is not None:
            if not self.connecting or (self.connecting and card_id != self.connection_start):
                if self.current_hover != card_id:
                    pass
                if self.current_hover != card_id:
                    self.app.canvas.configure(cursor="hand2")
                    self.current_hover = card_id
        else:
            if self.current_hover:
                self.app.canvas.configure(cursor="")
                self.current_hover = None
        
        if self.connecting and self.temp_line and self.connection_start:
            # Get starting position based on connection type
            if self.connection_start in self.app.people:
                start_obj = self.app.people[self.connection_start]
            else:
                start_obj = self.app.textboxes[self.connection_start]
            
            zoom = self.last_zoom
            start_x, start_y = start_obj.x * zoom, start_obj.y * zoom
            canvas_x = self.app.canvas.canvasx(event.x)
            canvas_y = self.app.canvas.canvasy(event.y)
            self.app.canvas.coords(self.temp_line, start_x, start_y, canvas_x, canvas_y)
            
            if card_id is not None and card_id != self.connection_start:
                self.app.canvas.itemconfig(self.temp_line, fill=COLORS['success'], width=4)
            else:
                self.app.canvas.itemconfig(self.temp_line, fill=COLORS['accent'], width=3)
    
    def on_right_click(self, event):
        """Improved right-click linking with more forgiving detection"""
        tolerance = 10
        
        canvas_x = self.app.canvas.canvasx(event.x)
        canvas_y = self.app.canvas.canvasy(event.y)
        
        items = self.app.canvas.find_overlapping(canvas_x - tolerance, canvas_y - tolerance, 
                                           canvas_x + tolerance, canvas_y + tolerance)
        card_id = None
        for item in items:
            tags = self.app.canvas.gettags(item)
            if any("person" in tag for tag in tags):
                for tag in tags:
                    if tag.startswith("person_"):
                        card_id = int(tag.split("_")[1])
                        break
                if card_id is not None:
                    break
            elif any("textbox" in tag for tag in tags):
                for tag in tags:
                    if tag.startswith("textbox_"):
                        card_id = int(tag.split("_")[1])
                        break
                if card_id is not None:
                    break
        if card_id is None:
            self.cancel_connection()
            return

        if not self.connecting:
            self.start_connection(card_id, canvas_x, canvas_y)
        elif self.connection_start == card_id:
            self.cancel_connection()
        else:
            self.complete_connection(card_id)
    
    def on_escape_key(self, event):
        """Handle escape key to cancel connections"""
        if self.connecting:
            self.cancel_connection()
            self.app.update_status("Connection cancelled with Escape key")
    
    def on_delete_key(self, event):
        """Handle delete key to remove selected connection, person, textbox, or legend"""
        if self.selected_connection:
            self.delete_connection()
        elif self.selected_person:
            self.app.delete_person()
        elif self.selected_textbox:
            self.app.delete_textbox()
        elif self.selected_legend:
            self.app.delete_legend()
    
    def on_color_cycle_key(self, event):
        """Handle 'c' key to cycle colors of selected person or textbox"""
        if self.selected_person:
            person = self.app.people[self.selected_person]
            person.color = (person.color + 1) % len(CARD_COLORS)
            
            if not self.dragging:
                self.app.refresh_person_widget(self.selected_person)
                self.app.update_status(f"Changed {person.name}'s color")
            else:
                self.app.update_status(f"Color will be updated for {person.name} after drag")
                self._pending_color_refresh = self.selected_person
        elif self.selected_textbox:
            textbox = self.app.textboxes[self.selected_textbox]
            textbox.color = (textbox.color + 1) % len(CARD_COLORS)
            
            if not self.dragging:
                self.app.refresh_textbox_widget(self.selected_textbox)
                self.app.update_status(f"Changed textbox '{textbox.title}' color")
            else:
                self.app.update_status(f"Color will be updated for textbox '{textbox.title}' after drag")
                self._pending_color_refresh = self.selected_textbox

    def on_middle_button_press(self, event):
        self.app.canvas.scan_mark(event.x, event.y)
        self._panning = True

    def on_middle_button_motion(self, event):
        if self._panning:
            self.app.canvas.scan_dragto(event.x, event.y, gain=1)

    def on_middle_button_release(self, event):
        self._panning = False

    def on_mouse_wheel(self, event):
        """Handle mouse wheel events to change the zoom slider"""
        current_zoom = self.app.zoom_var.get()
        zoom_step = 0.05
        new_zoom = min(current_zoom + zoom_step, 1.0) if event.delta > 0 else max(current_zoom - zoom_step, 0.5)
        self.app.zoom_var.set(new_zoom)
        self.on_zoom(new_zoom)

    def start_connection(self, card_id, x, y):
        """Start drawing a connection line from a card (person or textbox)"""
        self.connecting = True
        self.connection_start = card_id
        
        # Get the card object and name
        if card_id in self.app.people:
            card_obj = self.app.people[card_id]
            card_name = card_obj.name
        else:
            card_obj = self.app.textboxes[card_id]
            card_name = card_obj.title
            
        zoom = self.last_zoom
        start_x, start_y = card_obj.x * zoom, card_obj.y * zoom
        self.temp_line = self.app.canvas.create_line(start_x, start_y, x, y, fill=COLORS['accent'], width=3, dash=(4, 4))
        self.app.update_status(f"🔗 Connecting from {card_name}... Right-click another card to link, or right-click again to cancel.")
        self.app.canvas_helpers.highlight_card_for_connection(card_id)

    def complete_connection(self, card_id):
        """Complete a connection between two cards (people or textboxes)"""
        if not self.connecting or self.connection_start is None:
            return
            
        id1 = self.connection_start
        id2 = card_id
        
        # Avoid self-connection
        if id1 == id2:
            self.cancel_connection()
            return
        
        # Get card objects
        card1 = self.app.people.get(id1) or self.app.textboxes.get(id1)
        card2 = self.app.people.get(id2) or self.app.textboxes.get(id2)
        
        if not card1 or not card2:
            self.cancel_connection()
            return
            
        # Check if connection already exists
        if id2 in card1.connections:
            messagebox.showinfo("Connection Exists", "These two cards are already connected.")
            self.cancel_connection()
            return
            
        # Ask for a label for the connection
        dialog = ConnectionLabelDialog(self.app.root, "Add Connection Label")
        self.app.root.wait_window(dialog.dialog)
        label = dialog.result if dialog.result else ""
        
        # Add connection to data structures
        card1.connections[id2] = label
        card2.connections[id1] = label
        
        # Draw the final connection line
        self.app.draw_connection(id1, id2, label, self.last_zoom)
        
        # Clean up
        self.cancel_connection()
        
        # Get card names for status
        name1 = card1.name if hasattr(card1, 'name') else card1.title
        name2 = card2.name if hasattr(card2, 'name') else card2.title
        self.app.update_status(f"✅ Linked {name1} and {name2}")

    def cancel_connection(self):
        """Cancel the connection drawing process"""
        if self.temp_line:
            self.app.canvas.delete(self.temp_line)
            self.temp_line = None
        if self.connection_start:
            self.app.canvas_helpers.unhighlight_card_for_connection(self.connection_start)
        self.connecting = False
        self.connection_start = None
        self.app.update_status("Ready")

    def edit_person(self, person_id):
        """Handle editing a person's details via a dialog."""
        if person_id in self.app.people:
            person = self.app.people[person_id]
            
            # Use a dialog to get updated information
            dialog = PersonDialog(self.app.root, 
                                  "Edit Person", 
                                  name=person.name, 
                                  dob=person.dob,
                                  alias=person.alias,
                                  address=person.address,
                                  phone=person.phone,
                                  files=person.files)
            self.app.root.wait_window(dialog.dialog)
            
            if dialog.result:
                # Update person data
                person.name = dialog.result['name']
                person.dob = dialog.result['dob']
                person.alias = dialog.result['alias']
                person.address = dialog.result['address']
                person.phone = dialog.result['phone']
                person.files = dialog.result['files']
                
                # Refresh the specific person's widget on the canvas
                self.app.refresh_person_widget(person_id)
                self.app.update_status(f"Updated details for {person.name}")

    def edit_textbox(self, textbox_id):
        """Handle editing a textbox's details via a dialog."""
        if textbox_id in self.app.textboxes:
            textbox = self.app.textboxes[textbox_id]
            
            # Use a dialog to get updated information
            dialog = TextboxDialog(self.app.root, 
                                  "Edit Textbox Card", 
                                  title=textbox.title, 
                                  content=textbox.content)
            self.app.root.wait_window(dialog.dialog)
            
            if dialog.result:
                # Update textbox data
                textbox.title = dialog.result['title']
                textbox.content = dialog.result['content']
                
                # Refresh the specific textbox's widget on the canvas
                self.app.refresh_textbox_widget(textbox_id)
                self.app.update_status(f"Updated textbox '{textbox.title}'")

    def edit_legend(self, legend_id):
        """Handle editing a legend's details via a dialog."""
        if legend_id in self.app.legends:
            legend = self.app.legends[legend_id]
            
            # Use a dialog to get updated information
            dialog = LegendDialog(self.app.root, 
                                 "Edit Legend Card", 
                                 legend_title=legend.title, 
                                 color_entries=legend.color_entries)
            self.app.root.wait_window(dialog.dialog)
            
            if dialog.result:
                # Update legend data
                legend.title = dialog.result['title']
                legend.color_entries = dialog.result['color_entries']
                
                # Refresh the specific legend's widget on the canvas
                self.app.refresh_legend_widget(legend_id)
                self.app.update_status(f"Updated legend '{legend.title}'")

    def edit_connection_label(self):
        """Edit the label of the selected connection"""
        if not self.selected_connection:
            return
            
        id1, id2 = self.selected_connection
        
        # Get card objects (could be person, textbox, or legend)
        card1 = self.app.people.get(id1) or self.app.textboxes.get(id1) or self.app.legends.get(id1)
        card2 = self.app.people.get(id2) or self.app.textboxes.get(id2) or self.app.legends.get(id2)
        
        if not card1 or not card2:
            return
            
        current_label = card1.connections.get(id2, "")
        
        dialog = ConnectionLabelDialog(self.app.root, "Edit Connection Label", initial_value=current_label)
        self.app.root.wait_window(dialog.dialog)
        
        if dialog.result is not None:
            new_label = dialog.result
            card1.connections[id2] = new_label
            card2.connections[id1] = new_label
            self.app.canvas_helpers.update_connections()
            
            # Get card names for status
            name1 = card1.name if hasattr(card1, 'name') else card1.title
            name2 = card2.name if hasattr(card2, 'name') else card2.title
            self.app.update_status(f"Connection label updated for {name1} and {name2}")
        
        self.clear_connection_selection()

    def delete_connection(self):
        """Delete the currently selected connection"""
        if not self.selected_connection:
            messagebox.showwarning("No Selection", "Please select a connection to delete.")
            return
            
        id1, id2 = self.selected_connection
        
        # Get card objects (could be person, textbox, or legend)
        card1 = self.app.people.get(id1) or self.app.textboxes.get(id1) or self.app.legends.get(id1)
        card2 = self.app.people.get(id2) or self.app.textboxes.get(id2) or self.app.legends.get(id2)
        
        if not card1 or not card2:
            return
            
        # Get card names for display
        name1 = card1.name if hasattr(card1, 'name') else card1.title
        name2 = card2.name if hasattr(card2, 'name') else card2.title
        
        result = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete the connection between {name1} and {name2}?",
            icon='warning'
        )
        
        if result:
            # Remove from data structures
            if id2 in card1.connections:
                del card1.connections[id2]
            if id1 in card2.connections:
                del card2.connections[id1]
            
            # Remove from canvas
            if self.selected_connection in self.app.connection_lines:
                line_id, label_id, clickable_area_id, bg_rect_id = self.app.connection_lines.pop(self.selected_connection)
                self.app.canvas.delete(line_id)
                if label_id:
                    self.app.canvas.delete(label_id)
                if bg_rect_id:
                    self.app.canvas.delete(bg_rect_id)
                self.app.canvas.delete(clickable_area_id)
            
            self.selected_connection = None
            self.app.update_status(f"🗑️ Connection between {name1} and {name2} deleted")

    def highlight_connection_selection(self):
        """Highlight the selected connection on the canvas"""
        if not self.selected_connection:
            return
        
        if self.selected_connection in self.app.connection_lines:
            line_id, label_id, _, bg_rect_id = self.app.connection_lines[self.selected_connection]
            self.app.canvas.itemconfig(line_id, fill=COLORS['primary'], width=4)
            if label_id and bg_rect_id:
                self.app.canvas.itemconfig(bg_rect_id, outline=COLORS['primary'], width=2)

    def clear_connection_selection(self):
        """Clear any existing connection selection highlight"""
        if not self.selected_connection:
            return
            
        if self.selected_connection in self.app.connection_lines:
            line_id, label_id, _, bg_rect_id = self.app.connection_lines[self.selected_connection]
            self.app.canvas.itemconfig(line_id, fill=COLORS['text_secondary'], width=2)
            if label_id and bg_rect_id:
                self.app.canvas.itemconfig(bg_rect_id, outline=COLORS['border'])

        self.selected_connection = None
