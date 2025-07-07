#!/usr/bin/env python3
"""
Test script to verify textbox card functionality
This script will programmatically test the key features of textbox cards
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.models import TextboxCard, Person
import unittest

class TestTextboxFunctionality(unittest.TestCase):
    """Test cases for textbox card functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.textbox1 = TextboxCard("Important Notes", "This is some important content\nWith multiple lines")
        self.textbox2 = TextboxCard("Meeting Notes", "Meeting with client on 2024-01-15")
        self.person1 = Person("John Doe", "1990-01-01", "Johnny", "123 Main St", "555-0123")
        
        # Simulate how IDs are handled in the main app
        self.textbox1_id = "tb1"
        self.textbox2_id = "tb2"
        self.person1_id = "p1"
    
    def test_textbox_creation(self):
        """Test basic textbox card creation"""
        self.assertEqual(self.textbox1.title, "Important Notes")
        self.assertEqual(self.textbox1.content, "This is some important content\nWith multiple lines")
        self.assertEqual(len(self.textbox1.connections), 0)
    
    def test_textbox_connections(self):
        """Test connections between textboxes and other cards"""
        # Test textbox to textbox connection
        self.textbox1.add_connection(self.textbox2_id, "related")
        self.assertIn(self.textbox2_id, self.textbox1.connections)
        self.assertEqual(self.textbox1.connections[self.textbox2_id], "related")
        
        # Test textbox to person connection
        self.textbox1.add_connection(self.person1_id, "about")
        self.assertIn(self.person1_id, self.textbox1.connections)
        self.assertEqual(self.textbox1.connections[self.person1_id], "about")
    
    def test_textbox_removal(self):
        """Test connection removal"""
        self.textbox1.add_connection(self.textbox2_id, "test")
        self.textbox1.remove_connection(self.textbox2_id)
        self.assertNotIn(self.textbox2_id, self.textbox1.connections)
    
    def test_textbox_dict_conversion(self):
        """Test conversion to and from dictionary"""
        # Add a connection for more complete testing
        self.textbox1.add_connection(self.textbox2_id, "related")
        
        # Convert to dict
        textbox_dict = self.textbox1.to_dict()
        expected_keys = ['title', 'content', 'x', 'y', 'color', 'connections']
        for key in expected_keys:
            self.assertIn(key, textbox_dict)
        
        # Convert from dict
        new_textbox = TextboxCard.from_dict(textbox_dict)
        self.assertEqual(new_textbox.title, self.textbox1.title)
        self.assertEqual(new_textbox.content, self.textbox1.content)
        self.assertEqual(new_textbox.connections, self.textbox1.connections)

def run_tests():
    """Run all tests"""
    print("Running textbox card functionality tests...")
    unittest.main(verbosity=2, exit=False)

if __name__ == "__main__":
    run_tests()
    print("\n✅ All tests completed!")
