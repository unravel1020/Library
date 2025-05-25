# Smart Library Digital Twin System

## Overview
This project implements a digital twin system for a smart library, featuring real-time seat status display and smooth transition effects between different library views.

## Project Structure
```
smart_library/
├── backend/                  # Python FastAPI backend
│   ├── app.py                # FastAPI main entry
│   ├── models.py             # Data models (e.g., SeatStatus)
│   ├── database.py           # Database operations
│   ├── websocket.py          # WebSocket communication
│   ├── engine_control.py     # Brightness control/engine integration
│   └── requirements.txt      # Backend dependencies
├── frontend/                 # React frontend
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   └── SeatStatusBadge.jsx  # Seat status badge component
│   │   ├── App.jsx
│   │   └── index.js
│   ├── package.json
│   └── threejs/              # Three.js related code
├── README.md
└── docker-compose.yml        # One-click deployment (optional)
```

## Setup Instructions
1. **Backend Setup**
   - Navigate to the `backend` directory.
   - Install dependencies: `pip install -r requirements.txt`
   - Run the FastAPI server: `uvicorn app:app --reload`

2. **Frontend Setup**
   - Navigate to the `frontend` directory.
   - Install dependencies: `npm install`
   - Start the development server: `npm start`

## Usage
- Access the API at `http://localhost:8000/api/seat_status/{library_id}` to get seat status.
- WebSocket endpoint: `ws://localhost:8000/ws/seat_status/{library_id}` for real-time updates.
- The frontend displays seat status with color-coded badges (green for available, red for occupied, yellow for reserved).

## Notes
- Ensure the database (`library.db`) is properly initialized with the `seat_status` table.
- For production, consider using a more robust database like MySQL or PostgreSQL.
- The brightness transition effect is implemented in the frontend using Three.js. 