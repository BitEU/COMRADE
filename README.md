# 🔗 COMRADE - Connection Object Mapping and Relational Assessment Database Engine 

A modern, interactive Python GUI application for visualizing and managing complex relationship networks between people, textboxes, and legend cards. COMRADE provides an intuitive interface for creating, editing, and exploring connection networks with a beautiful, modern design and powerful data management capabilities.

## 📋 Table of Contents

- [🔗 COMRADE](#-comrade---connection-object-mapping-and-relational-assessment-database-engine)
  - [📋 Table of Contents](#-table-of-contents)
  - [✨ Features](#-features)
  - [🚀 Getting Started](#-getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
    - [Running the Application](#running-the-application)
  - [💻 Usage](#-usage)
    - [Adding Content](#adding-content)
    - [Creating Connections](#creating-connections)
    - [Editing Information](#editing-information)
    - [Navigation Controls](#navigation-controls)
    - [Data Management](#data-management)
    - [Clipboard Operations](#clipboard-operations)
  - [🎨 Interface Overview](#-interface-overview)
  - [🔧 Technical Details](#-technical-details)
    - [Architecture](#architecture)
    - [Dependencies](#dependencies)
    - [Data Format](#data-format)
  - [⌨️ Keyboard Shortcuts](#️-keyboard-shortcuts)
  - [🎯 Features in Detail](#-features-in-detail)
    - [Card Management](#card-management)
    - [Connection System](#connection-system)
    - [Visual Design](#visual-design)
    - [Zoom and Pan](#zoom-and-pan)
    - [File Attachments](#file-attachments)
  - [ℹ️ Frequently Asked Questions](#ℹ️-frequently-asked-questions)
  - [📄 License](#-license)
  - [🤝 Contributing](#-contributing)

## ✨ Features

### **🃏 Multi-Card System**
- **👤 Person Cards**: Comprehensive people profiles with detailed information
- **📝 Textbox Cards**: Rich text content cards for notes, documentation, and context
- **📊 Legend Cards**: Color-coded legend system for visual organization

### **👤 Person Management**
- Full Name, Date of Birth, Alias/Nickname
- Address, Phone Number, SSN, Email
- File attachments (images, documents, etc.)
- Profile picture support with auto-resizing
- Color-coding system with cycling colors

### **📝 Content Management**
- Rich textbox cards with title and content areas
- Legend cards with customizable color-coding system
- Comprehensive note-taking capabilities
- Visual organization tools

### **🔗 Advanced Connection System**
- **Interactive Creation**: Right-click to start/complete connections
- **Universal Connections**: Connect any card type to any other card type
- **Labeled Relationships**: Custom connection labels with visual styling
- **Connection Editing**: Double-click labels to edit descriptions
- **Visual Feedback**: Highlighted cards during connection mode

### **🎨 Modern UI Design**
- **Card-Based Design**: Beautiful cards with shadows, rounded corners, and professional styling
- **Color System**: Consistent color coding across all card types
- **Hover Effects**: Smooth visual feedback and interaction cues
- **Modern Typography**: Clean Segoe UI font family throughout
- **Professional Theme**: Carefully crafted color palette and spacing

### **🔍 Interactive Canvas**
- **Advanced Zoom**: Smooth zoom with mouse wheel (0.5x to 1.0x range)
- **Pan Navigation**: Middle mouse button dragging for canvas navigation
- **Drag & Drop**: Intuitive repositioning of all card types
- **Grid System**: Visual alignment grid with zoom-aware scaling
- **Smart Positioning**: Auto-placement of new cards at (500, 500)

### **📋 Clipboard System**
- **Copy/Cut/Paste**: Full clipboard support for all card types
- **Smart Positioning**: Paste cards at mouse cursor location
- **Data Preservation**: Maintains card data while clearing connections
- **Cross-Session**: Clipboard persists during application session

### **💾 Robust Data Management**
- **ZIP Project Format**: Complete project packaging with file attachments
- **Legacy Support**: Backward compatibility with CSV format
- **File Organization**: Automatic extraction and cleanup of attached files
- **Fuzzy Name Detection**: Warns about similar card names to prevent duplicates
- **Auto-Updates**: Built-in update checking system

### **🔧 Performance Optimizations**
- **Efficient Rendering**: Direct canvas manipulation during drag operations
- **Image Caching**: LRU cache for scaled images to improve zoom performance
- **Debounced Updates**: Optimized zoom and text scaling with 50ms debouncing
- **Memory Management**: Proper cleanup of canvas items and cached resources

## 🚀 Getting Started

### Prerequisites

- Python 3.7 or higher
- tkinter (usually included with Python)
- Pillow (PIL) for image handling and PNG export (recommended)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd COMRADE
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Running the Application

```bash
python main.py
```

## 💻 Usage

### Adding Content

#### **Person Cards**
1. Click **"👤 Add Person"** in the toolbar
2. Fill in personal information (name, DOB, address, etc.)
3. Attach files by clicking **"Attach Files"** and selecting documents/images
4. Click **"Save"** to add the person to the canvas

#### **Textbox Cards**
1. Click **"📝 Add Textbox"** in the toolbar
2. Enter a title and rich text content
3. Use textbox cards for notes, documentation, or contextual information
4. Click **"Save"** to add the textbox to the canvas

#### **Legend Cards**
1. Click **"📊 Edit Legend"** in the toolbar
2. Create color-coded entries to organize your network
3. Use legends to explain color meanings or categorize relationships
4. Click **"Save"** to update the legend

### Creating Connections

1. **Right-click** on any card to start a connection
2. The card will be highlighted and a temporary line will follow your mouse
3. **Right-click** on another card to complete the connection
4. Enter a label for the connection (e.g., "Friend", "Colleague", "Reports to")
5. Press **Escape** to cancel a connection in progress

### Editing Information

- **Double-click** any card to edit its information
- **Double-click** connection labels to edit relationship descriptions
- **Delete key** to remove selected connections or cards
- **C key** to cycle through colors for person and textbox cards

### Navigation Controls

- **Drag** any card to reposition it
- **Mouse wheel** to zoom in/out (0.5x to 1.0x range)
- **Middle mouse button + drag** to pan around the canvas
- **Zoom slider** in the status bar for precise zoom control

### Data Management

- **💾 Save Project**: Export complete network to ZIP file with all attachments
- **📁 Load Project**: Import previously saved projects (ZIP or legacy CSV)
- **🖼️ Export PNG**: Generate high-quality PNG image of your network
- **🗑️ Clear All**: Remove all content with confirmation dialog
- **🔄 Check Updates**: Automatic update checking with manual option

### Clipboard Operations

- **Ctrl+C**: Copy selected card to clipboard
- **Ctrl+X**: Cut selected card to clipboard  
- **Ctrl+V**: Paste card at mouse cursor position
- Cards are pasted without connections for clean network building

## 🎨 Interface Overview

The application features a sophisticated, modern interface:

- **Header Bar**: Application title and branding
- **Toolbar**: Primary action buttons with hover effects
- **Main Canvas**: Infinite workspace with grid overlay and zoom capabilities
- **Status Bar**: Real-time feedback, connection mode indicators, and zoom controls
- **Context Menus**: Right-click interactions for connection creation

## 🔧 Technical Details

### Architecture

The application follows a clean, modular architecture:

- **main.py**: Application entry point and main window management
- **src/models.py**: Data models (Person, TextboxCard, LegendCard)
- **src/event_handlers.py**: Comprehensive event handling and user interactions
- **src/canvas_helpers.py**: Canvas rendering, widget creation, and visual effects
- **src/ui_setup.py**: UI initialization and styling
- **src/data_management.py**: File I/O, project management, and persistence
- **src/dialogs.py**: Modal dialogs for data entry and editing
- **src/constants.py**: Color schemes and configuration constants
- **src/utils.py**: Utility functions and helpers

### Dependencies

- **tkinter**: GUI framework (Python standard library)
- **Pillow (PIL)**: Image processing and PNG export
- **csv**: Data persistence (Python standard library)
- **zipfile**: Project packaging (Python standard library)
- **logging**: Comprehensive application logging (Python standard library)
- **urllib**: Update checking functionality (Python standard library)

### Data Format

Projects are saved as ZIP files containing:

**data.csv structure:**
```csv
ID,Name,DOB,Alias,Address,Phone,SSN,Email,X,Y,Color,Files
1,John Doe,1990-01-01,Johnny,123 Main St,555-1234,123-45-6789,john@email.com,500,500,0,"photo.jpg;document.pdf"
TEXTBOXES
ID,Title,Content,X,Y,Color
1,Meeting Notes,Important discussion points...,600,300,1
LEGENDS  
ID,Title,Color_Entries,X,Y
1,Status Legend,"{""0"": ""Active"", ""1"": ""Inactive""}",700,100
CONNECTIONS
From_ID,To_ID,Label
1,2,Best Friend
```

**File Structure:**
```
project.zip
├── data.csv          # Network data
└── files/            # Attached images
    └── [supporting image files]
```

## ⌨️ Keyboard Shortcuts

| Key Combination | Action |
|-----------------|--------|
| **Left Click** | Select and drag cards |
| **Right Click** | Start/complete connections |
| **Double Click** | Edit cards or connection labels |
| **Escape** | Cancel connection mode or clear selection |
| **Delete/Backspace** | Delete selected connection or card |
| **C** | Cycle card colors (person/textbox cards) |
| **Ctrl+C** | Copy selected card |
| **Ctrl+X** | Cut selected card |
| **Ctrl+V** | Paste card at cursor |
| **Mouse Wheel** | Zoom in/out |
| **Middle Mouse + Drag** | Pan canvas |

## 🎯 Features in Detail

### Card Management
- **Three Card Types**: People, textboxes, and legends for comprehensive data organization
- **Rich Data Models**: Extensive information storage with validation
- **Visual Consistency**: Unified design language across all card types
- **Smart Defaults**: Automatic positioning and sensible default values

### Connection System
- **Universal Connectivity**: Any card can connect to any other card
- **Visual Connection Lines**: Clean, professional connection rendering
- **Interactive Labels**: Clickable, editable connection descriptions
- **Connection Management**: Easy creation, editing, and deletion

### Visual Design
- **Modern Aesthetics**: Card-based design with subtle shadows and rounded corners
- **Color Psychology**: Carefully chosen color palette for readability and professionalism
- **Responsive Interactions**: Smooth hover effects and visual feedback
- **Typography**: Consistent use of Segoe UI for optimal readability

### Zoom and Pan
- **Smooth Scaling**: Proportional zoom with maintained aspect ratios
- **Text Scaling**: Intelligent font scaling that preserves readability
- **Image Scaling**: High-quality image resizing with caching
- **Performance**: Optimized rendering for large networks

### File Attachments
- **Multiple Formats**: Support for images, documents, and various file types
- **Visual Preview**: Image thumbnails directly in person cards
- **File Management**: Automatic organization and cleanup
- **Package Integrity**: Complete project packaging with all dependencies

## ℹ️ Frequently Asked Questions

**Q: How can I import data from Excel or CSV files?**
A: You can import data by: (1) Extracting your .ZIP project file, editing the data.csv file, and inserting new rows above the CONNECTIONS section, or (2) Converting your data to the legacy CSV format (see /test_files/musicians.csv as an example) and loading it directly into COMRADE.

**Q: What file formats are supported for attachments?**
A: COMRADE supports common image formats (JPG, PNG, GIF, BMP, WebP) with thumbnail preview, and any document format for attachment. Images are automatically resized and displayed in person cards.

**Q: How does the color-coding system work?**
A: Each card type has a color-coding system. Person and textbox cards can cycle through different colors using the 'C' key, while legend cards are used to document what each color represents in your network.

**Q: What's the performance like with large networks?**
A: COMRADE is optimized for performance with features like image caching, debounced zoom updates, and efficient canvas rendering. It can handle substantial networks while maintaining smooth interactions. It isn't perfect, but it's pretty good.

**Q: Is the data format future-proof?**
A: Yes, COMRADE maintains backward compatibility with the legacy CSV format while using a modern ZIP-based project format. This ensures your data remains accessible across versions.

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests to improve COMRADE. The modular architecture makes it easy to extend functionality and add new features.