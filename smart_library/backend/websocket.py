from fastapi import WebSocket
from database import get_area_seats, get_library_areas, get_seat_status
from models import SeatType
import asyncio
from app import app
from typing import Dict, Set

# 存储活跃的WebSocket连接
active_connections: Dict[str, Set[WebSocket]] = {
    "library": set(),
    "area": set(),
    "seat": set()
}

@app.websocket("/ws/library/{library_id}")
async def library_websocket(websocket: WebSocket, library_id: int):
    await websocket.accept()
    active_connections["library"].add(websocket)
    try:
        while True:
            # 获取图书馆所有区域的状态
            areas = get_library_areas(library_id)
            status = {
                "areas": [
                    {
                        "id": area.id,
                        "name": area.name,
                        "floor": area.floor,
                        "total_seats": len(area.seats),
                        "available_seats": sum(1 for seat in area.seats if seat.is_available)
                    }
                    for area in areas
                ]
            }
            await websocket.send_json(status)
            await asyncio.sleep(1)
    except:
        active_connections["library"].remove(websocket)

@app.websocket("/ws/area/{area_id}")
async def area_websocket(websocket: WebSocket, area_id: int):
    await websocket.accept()
    try:
        while True:
            # 获取区域所有座位的状态
            seats = get_area_seats(area_id)
            status = {
                "seats": [
                    {
                        "id": seat.id,
                        "seat_number": seat.seat_number,
                        "is_available": seat.is_available
                    }
                    for seat in seats
                ]
            }
            await websocket.send_json(status)
            await asyncio.sleep(1)
    except:
        pass

@app.websocket("/ws/seat/{seat_id}")
async def seat_websocket(websocket: WebSocket, seat_id: int):
    await websocket.accept()
    active_connections["seat"].add(websocket)
    try:
        while True:
            # 获取单个座位的状态
            seat = get_seat_status(seat_id)
            if seat:
                status = {
                    "id": seat.id,
                    "seat_number": seat.seat_number,
                    "seat_type": seat.seat_type.value,
                    "is_available": seat.is_available,
                    "has_power": seat.has_power,
                    "has_computer": seat.has_computer,
                    "current_reservation": None  # 可以添加当前预约信息
                }
                await websocket.send_json(status)
            await asyncio.sleep(1)
    except:
        active_connections["seat"].remove(websocket)

# 广播更新给所有相关连接
async def broadcast_update(update_type: str, data: dict):
    if update_type in active_connections:
        for connection in active_connections[update_type]:
            try:
                await connection.send_json(data)
            except:
                active_connections[update_type].remove(connection) 