#!/usr/bin/env python3
"""
Test script to verify PNG export with images functionality
"""

import os
import sys
from PIL import Image, ImageDraw

def create_test_image(filename, text="Test Image"):
    """Create a simple test image for testing"""
    # Create a 200x200 test image
    img = Image.new('RGB', (200, 200), color='lightblue')
    draw = ImageDraw.Draw(img)
    
    # Draw some simple content
    draw.rectangle([10, 10, 190, 190], outline='darkblue', width=3)
    draw.text((50, 90), text, fill='darkblue')
    
    # Save the image
    img.save(filename)
    print(f"Created test image: {filename}")

def main():
    """Create test images for the COMRADE application"""
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create some test images
    test_images = [
        "test_person1.png",
        "test_person2.jpg", 
        "test_person3.png"
    ]
    
    for i, img_name in enumerate(test_images, 1):
        img_path = os.path.join(test_dir, img_name)
        create_test_image(img_path, f"Person {i}")
    
    print("\nTest images created successfully!")
    print("You can now:")
    print("1. Run the COMRADE application")
    print("2. Add people to the network")
    print("3. Attach these test images to people using the file attachment feature")
    print("4. Export to PNG to verify images are included")

if __name__ == "__main__":
    main()
