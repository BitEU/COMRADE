# 🔗 COMRADE - Connection Object Mapping and Relational Assessment Database Engine 

A modern, interactive Python GUI application for visualizing and managing relationships between people. COMRADE provides an intuitive interface for creating, editing, and exploring connection networks with a beautiful, modern design.

## 📋 Table of Contents

- [🔗 COMRADE](#-comrade---people-connection-visualizer)
  - [📋 Table of Contents](#-table-of-contents)
  - [✨ Features](#-features)
  - [🚀 Getting Started](#-getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
    - [Running the Application](#running-the-application)
  - [💻 Usage](#-usage)
    - [Adding People](#adding-people)
    - [Creating Connections](#creating-connections)
    - [Editing Information](#editing-information)
    - [Navigation Controls](#navigation-controls)
    - [Data Management](#data-management)
  - [🎨 Interface Overview](#-interface-overview)
  - [📁 Project Structure](#-project-structure)
  - [🔧 Technical Details](#-technical-details)
    - [Architecture](#architecture)
    - [Dependencies](#dependencies)
    - [Data Format](#data-format)
  - [⌨️ Keyboard Shortcuts](#️-keyboard-shortcuts)
  - [🎯 Features in Detail](#-features-in-detail)
    - [Person Management](#person-management)
    - [Connection System](#connection-system)
    - [Visual Design](#visual-design)
    - [Zoom and Pan](#zoom-and-pan)
  - [📄 License](#-license)
  - [🤝 Contributing](#-contributing)

## ✨ Features

- **👤 Person Management**: Add, edit, and manage detailed person profiles with information including:
  - Full Name
  - Date of Birth
  - Alias/Nickname
  - Address
  - Phone Number
  - File attachments (images, documents, etc.)

- **🔗 Connection Visualization**: Create and manage labeled relationships between people
  - Interactive connection creation via right-click
  - Customizable connection labels
  - Visual connection lines with editable labels

- **🎨 Modern UI Design**: Beautiful, modern interface with:
  - Card-based person display with rounded corners and shadows
  - Color-coded elements with professional color scheme
  - Smooth hover effects and visual feedback
  - Responsive design elements

- **🔍 Interactive Canvas**: Full-featured canvas with:
  - Drag-and-drop person positioning
  - Zoom in/out functionality with mouse wheel
  - Pan with middle mouse button
  - Grid overlay for alignment
  - Auto-layout for new people

- **💾 Data Persistence**: Robust data management with:
  - Save/Load projects in ZIP format with file attachments
  - Backward compatibility with legacy CSV format
  - Automatic file organization and cleanup
  - Preserves all relationships and positioning

- **⌨️ Keyboard Controls**: Full keyboard support for efficient workflow

## 🚀 Getting Started

### Prerequisites

- Python 3.7 or higher
- tkinter (usually included with Python)
- Optional: Pillow (PIL) for PNG export functionality

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

### Adding People

1. Click the **"👤 Add Person"** button in the toolbar
2. Fill in the person's information in the dialog box
3. Click **"Save"** to add the person to the canvas

### Creating Connections

1. **Right-click** on a person card to start a connection
2. The person will be highlighted and a temporary line will follow your mouse
3. **Right-click** on another person to complete the connection
4. Enter a label for the connection (e.g., "Friend", "Colleague", "Family")
5. Press **Escape** to cancel a connection in progress

### Editing Information

- **Double-click** on a person card to edit their information
- **Double-click** on a connection label to edit the relationship description
- Use the **Delete** key to remove selected connections
- Press **c** to change the color of a person card

### Navigation Controls

- **Drag** person cards to reposition them
- **Mouse wheel** to zoom in/out
- **Middle mouse button + drag** to pan around the canvas
- **Zoom slider** in the bottom-right for precise zoom control

### Data Management

- **💾 Save Project**: Export your network to a ZIP file containing:
  - Network data (CSV format)
  - All attached images and files
  - Preserves all relationships and positioning
- **📁 Load Project**: Import a previously saved project
  - Supports new ZIP format with file attachments
  - Backward compatible with legacy CSV files
  - Automatically extracts attached files to local storage
- **🗑️ Clear All**: Remove all people and connections (with confirmation)

## 🎨 Interface Overview

The application features a clean, modern interface divided into several sections:

- **Header**: Application title and main navigation
- **Toolbar**: Quick access buttons for primary actions
- **Canvas**: Main visualization area with grid overlay
- **Instructions Panel**: Helpful usage tips
- **Status Bar**: Current mode and zoom controls

## 📁 Project Structure

```
COMRADE/
├── main.py              # Main application file with ConnectionApp class
├── models.py            # Person data model
├── dialogs.py           # Dialog classes for person and connection editing
├── constants.py         # Application constants and color scheme
├── based.csv           # Sample data file
├── LICENSE             # GNU General Public License v3.0
└── README.md           # This file
```

## 🔧 Technical Details

### Architecture

The application follows a modular architecture:

- **ConnectionApp**: Main application class handling UI and logic
- **Person**: Data model for individual people
- **PersonDialog**: Modal dialog for adding/editing person information
- **ConnectionLabelDialog**: Modal dialog for editing connection labels

### Dependencies

- **tkinter**: GUI framework (Python standard library)
- **csv**: Data persistence (Python standard library)
- **logging**: Application logging (Python standard library)

### Data Format

Data is saved in CSV format with the following structure:

```csv
ID,Name,DOB,Alias,Address,Phone,X,Y
1,John Doe,1990-01-01,Johnny,123 Main St,555-1234,100,200
CONNECTIONS
From_ID,To_ID,Label
1,2,Best Friend
```

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **Escape** | Cancel connection mode |
| **Delete** | Delete selected connection |
| **Backspace** | Delete selected connection |
| **Enter** | Confirm dialog input |
| **Double-click** | Edit person or connection |
| **c** | Edit person card color |

## 🎯 Features in Detail

### Person Management
- Comprehensive person profiles with multiple data fields
- Visual cards with emoji icons for easy identification
- Automatic positioning with smart layout algorithm
- Hover effects for improved user experience

### Connection System
- Intuitive right-click connection creation
- Labeled relationships with custom descriptions
- Visual connection lines with clickable labels
- Connection editing and deletion capabilities

### Visual Design
- Modern card-based design with shadows and rounded corners
- Professional color scheme with consistent theming
- Responsive hover effects and visual feedback
- Clean typography with Segoe UI font family

### Zoom and Pan
- Smooth zoom functionality with mouse wheel
- Pan capabilities with middle mouse button
- Zoom slider for precise control
- Maintains aspect ratios and text readability

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests to improve COMRADE.