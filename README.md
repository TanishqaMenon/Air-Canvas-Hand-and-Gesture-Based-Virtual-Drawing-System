Air Canvas Ultra Pro: Gesture-Based Virtual Drawing System

Air Canvas Ultra Pro is an advanced computer vision–based application that enables users to draw, paint, and interact with a digital canvas using only hand gestures—no mouse, stylus, or touch input required.

📌 Project Overview

Air Canvas Ultra Pro uses real-time hand tracking to convert finger movements into drawing actions. By leveraging computer vision and gesture recognition, the system creates an intuitive and touch-free drawing experience.
The application supports multiple tools, shapes, colors, and gesture-based controls, making it a powerful virtual drawing system.

🎯 Key Features

✋ Hand Gesture Recognition – Detects and tracks hand landmarks using MediaPipe

🎨 Virtual Drawing Canvas – Draw in real-time using finger movements

🖌️ Brush & Eraser Tools – Adjustable sizes with gesture control

🎨 Color Palette – Wide range of selectable colors

📐 Shape Drawing Tools – Line, Rectangle, Circle

🔄 Undo / Redo Functionality – Supports up to 20 steps

🤏 Pinch Gesture Control – Resize brush/eraser using 3-finger pinch

💾 Save Canvas – Export drawings as image files

🖥️ Interactive UI Panel – Toolbars, palette, and controls

🌐 Web Integration (Flask) – Launch drawing via web interface

🏗️ System Architecture

The system follows this pipeline:

• Capture video from webcam

• Detect hand landmarks using MediaPipe

• Identify finger gestures

• Map gestures to drawing actions

• Render drawings on virtual canvas

• Overlay UI (tools, colors, controls)

• Display final output in real-time

🛠️ Technologies Used

Frontend:

• HTML

• CSS

• JavaScript

Backend:

• Python (Flask)

Computer Vision:

• OpenCV

• MediaPipe

Data Handling:

• NumPy

📂 Project Structure

AIRCANVAS...
│
├── templates/
│   └── index.html
│
├── air_canvas_backend.py
└── app.py

🎮 Gesture Controls

Gesture	Action

• ☝ 1 Finger	Draw / Erase / Drag

• ✌ 2 Fingers	Select tool / UI

• 🤌  3-Finger Pinch	Resize brush/eraser

• ✋  No Hand	Idle

⌨️ Keyboard Shortcuts

Key	Function

ESC	Exit

📸 Screenshots
 <img width="958" height="468" alt="image" src="https://github.com/user-attachments/assets/cb2f6c17-d2d7-46d4-9ccb-99e7c49dc251" />



⚠️ Limitations

• Requires a webcam for operation

• Works best in good lighting conditions

• No multi-user support

• Limited gesture set

• No cloud save or sharing

🚀 Future Scope

• AI-based gesture recognition improvement

• Multi-hand support

• Mobile app integration

• Cloud storage for drawings

• Voice command integration

• Advanced shape recognition (freehand → perfect shapes)

• Collaboration (multi-user drawing)

👩‍💻 Contributors

R.P.Tanishqa Menon

Noushin Naufal

Neona Rose Joyal Mattam

Noor Fathima

📜 License

This project is developed for academic and learning purposes.
