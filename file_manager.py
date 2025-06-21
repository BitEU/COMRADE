# file_manager.py
"""
File Manager - Handles saving and loading data
"""

import csv
import logging
from tkinter import filedialog, messagebox
from models import Person

logger = logging.getLogger(__name__)

class FileManager:
    """Manages file operations for saving and loading data"""
    
    def __init__(self, app):
        self.app = app
    
    def save_data(self):
        """Save current data to CSV file"""
        # Ask for filename
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Connection Data"
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                
                # Write header
                writer.writerow(['Type', 'ID', 'Name', 'DOB', 'Alias', 'Address', 'Phone', 'X', 'Y'])
                
                # Write people data
                for person_id, person in self.app.people.items():
                    writer.writerow([
                        'PERSON',
                        person_id,
                        person.name,
                        person.dob,
                        person.alias,
                        person.address,
                        person.phone,
                        person.x,
                        person.y
                    ])
                
                # Write connections header
                writer.writerow([])
                writer.writerow(['Type', 'From_ID', 'To_ID', 'Label'])
                
                # Write connections (avoid duplicates)
                written_connections = set()
                for person_id, person in self.app.people.items():
                    for connected_id, label in person.connections.items():
                        # Create a key that's the same regardless of order
                        connection_key = tuple(sorted([person_id, connected_id]))
                        
                        if connection_key not in written_connections:
                            writer.writerow([
                                'CONNECTION',
                                person_id,
                                connected_id,
                                label
                            ])
                            written_connections.add(connection_key)
            
            self.app.ui_manager.update_status(f"✅ Saved to {filename}")
            logger.info(f"Data saved to {filename}")
            
        except Exception as e:
            messagebox.showerror(
                "Save Error",
                f"Failed to save data: {str(e)}",
                parent=self.app.root
            )
            logger.error(f"Error saving data: {e}")
    
    def load_data(self):
        """Load data from CSV file"""
        # Ask for filename
        filename = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Load Connection Data"
        )
        
        if not filename:
            return
        
        try:
            # Clear existing data
            self.app.canvas_manager.clear_all()
            self.app.people.clear()
            
            with open(filename, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                
                # Skip header
                next(reader)
                
                # Read people
                max_id = 0
                for row in reader:
                    if not row or row[0] != 'PERSON':
                        break
                    
                    person_id = int(row[1])
                    person = Person(
                        name=row[2],
                        dob=row[3],
                        alias=row[4],
                        address=row[5],
                        phone=row[6]
                    )
                    person.x = float(row[7])
                    person.y = float(row[8])
                    
                    self.app.people[person_id] = person
                    max_id = max(max_id, person_id)
                
                # Update next ID
                self.app.next_id = max_id + 1
                
                # Skip empty row and connections header
                next(reader, None)
                
                # Read connections
                for row in reader:
                    if row and row[0] == 'CONNECTION':
                        from_id = int(row[1])
                        to_id = int(row[2])
                        label = row[3]
                        
                        # Add connection to both people
                        if from_id in self.app.people and to_id in self.app.people:
                            self.app.people[from_id].connections[to_id] = label
                            self.app.people[to_id].connections[from_id] = label
            
            # Redraw all elements
            for person_id in self.app.people:
                self.app.canvas_manager.create_person_widget(person_id)
                logger.info(f"Created widget for loaded person {person_id}: {self.app.people[person_id].name}")
            
            # Draw all connections
            drawn_connections = set()
            for person_id, person in self.app.people.items():
                for connected_id, label in person.connections.items():
                    connection_key = tuple(sorted([person_id, connected_id]))
                    if connection_key not in drawn_connections:
                        self.app.canvas_manager.draw_connection(person_id, connected_id, label)
                        drawn_connections.add(connection_key)
            
            self.app.ui_manager.update_status(f"✅ Loaded from {filename}")
            logger.info(f"Data loaded from {filename}")
            
        except Exception as e:
            messagebox.showerror(
                "Load Error",
                f"Failed to load data: {str(e)}",
                parent=self.app.root
            )
            logger.error(f"Error loading data: {e}")