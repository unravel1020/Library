from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import FileResponse
from models import (
    Base, SeatType, ReservationStatus, LogLevel, NotificationType,
    NotificationStatus, Notification, NotificationTemplate,
    ReportType, ReportFormat, Report, SystemConfig, LibrarySchedule, ReservationRule, User,
    Area, Seat, Reminder, ReservationStats, Blacklist, PointsHistory
)
import database # Import the entire database module
from database import process_notifications # Explicitly import the function
from datetime import datetime, timedelta
import asyncio
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr
import os
from dotenv import load_dotenv
import hashlib
import tempfile
import json

app = FastAPI()
database.init_db() # Call init_db using the module prefix

# 密码加密和 JWT 配置
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
SECRET_KEY = "your-secret-key"  # 生产环境应使用环境变量
ALGORITHM = "HS256"

def create_access_token(data: dict):
    to_encode = data.copy()
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(status_code=401, detail="Invalid credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return user_id

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = database.verify_user(form_data.username, form_data.password) # Call verify_user using the module prefix
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    access_token = create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/seat_status/{library_id}")
def api_get_seat_status(library_id: str):
    status = database.get_seat_status(library_id) # Call get_seat_status using the module prefix
    if status:
        return {
            "available": status.available_seats, # Use correct attribute names from Library model
            "occupied": status.occupied_seats,
            "reserved": status.reserved_seats
        }
    raise HTTPException(status_code=404, detail="Library not found")

@app.post("/api/seat_status/{library_id}")
def api_update_seat_status(library_id: str, available: int, occupied: int, reserved: int, current_user: str = Depends(get_current_user)):
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    database.update_seat_status(library_id, available, occupied, reserved) # Call update_seat_status using the module prefix
    return {"msg": "Seat status updated"}

@app.get("/api/libraries")
def api_get_libraries():
    return [ {"id": lib.id, "name": lib.name, "address": lib.location} for lib in database.get_all_libraries() ] # Call get_all_libraries using the module prefix, use correct attribute name location

@app.post("/api/libraries")
def api_add_library(id: str, name: str, address: str, current_user: str = Depends(get_current_user)):
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    database.add_library(id, name, address) # Call add_library using the module prefix
    return {"msg": "Library added"}

class ReservationCreate(BaseModel):
    seat_id: int
    start_time: datetime
    end_time: datetime

class ReservationResponse(BaseModel):
    id: int
    seat_id: int
    user_id: int
    start_time: datetime
    end_time: datetime
    status: ReservationStatus
    created_at: datetime

class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None

class StatsResponse(BaseModel):
    total: Optional[int] = None # Make total optional for flexible stats response
    by_status: Optional[Dict[str, int]] = None # Make by_status optional
    by_type: Optional[Dict[str, int]] = None # Make by_type optional
    total_seats: Optional[int] = None # Add total_seats for area stats
    reservations: Optional[Dict[str, int]] = None # Add reservations for area stats

@app.post("/reservations", response_model=ReservationResponse)
async def create_reservation(
    reservation: ReservationCreate,
    current_user: str = Depends(get_current_user)
):
    current_user_id = int(current_user)
    try:
        return database.create_reservation(
            current_user_id,
            reservation.seat_id,
            reservation.start_time,
            reservation.end_time
        ) # Call create_reservation using the module prefix
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/reservations/user/{user_id}", response_model=List[ReservationResponse])
async def get_user_reservations(
    user_id: int,
    status: Optional[ReservationStatus] = None,
    current_user: str = Depends(get_current_user)
):
    current_user_id = int(current_user)
    if user_id != current_user_id and not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    return database.get_user_reservations(user_id, status) # Call get_user_reservations using the module prefix

@app.get("/reservations/seat/{seat_id}", response_model=List[ReservationResponse])
async def get_seat_reservations(
    seat_id: int,
    status: Optional[ReservationStatus] = None
):
    return database.get_seat_reservations(seat_id, status) # Call get_seat_reservations using the module prefix

@app.get("/stats/area/{area_id}", response_model=StatsResponse)
async def get_area_stats(
    area_id: int,
    start_date: datetime,
    end_date: datetime,
    current_user: str = Depends(get_current_user)
):
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    stats = database.get_area_usage_stats(area_id, start_date, end_date) # Call get_area_usage_stats using the module prefix
    return StatsResponse(total_seats=stats["total_seats"], reservations=stats["reservations"]) # Map keys to StatsResponse

@app.get("/stats/user/{user_id}", response_model=StatsResponse)
async def get_user_stats(
    user_id: int,
    start_date: datetime,
    end_date: datetime,
    current_user: str = Depends(get_current_user)
):
    current_user_id = int(current_user)
    if user_id != current_user_id and not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    stats = database.get_user_reservation_stats(user_id, start_date, end_date) # Call get_user_reservation_stats using the module prefix
    return StatsResponse(total=stats["total"], by_status=stats["by_status"])

@app.put("/users/{user_id}")
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: str = Depends(get_current_user)
):
    current_user_id = int(current_user)
    if user_id != current_user_id and not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    
    session = database.SessionLocal() # Call SessionLocal using the module prefix
    try:
        user = session.query(database.User).filter(database.User.id == user_id).first() # Use database.User
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user_update.username:
            user.username = user_update.username
        if user_update.password:
            user.password = hashlib.sha256(user_update.password.encode()).hexdigest()
        
        session.commit()
        return {"message": "User updated successfully"}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

@app.post("/api/users")
def api_create_user(username: str, password: str, role: str = "user"):
    database.create_user(username, password, role) # Call create_user using the module prefix
    return {"msg": "User created"}

@app.post("/api/reminders")
def api_create_reminder(reservation_id: int, reminder_time: datetime, current_user: str = Depends(get_current_user)):
    current_user_id = int(current_user)
    database.create_reminder(reservation_id, current_user_id, reminder_time) # Call create_reminder using the module prefix
    return {"msg": "Reminder created"}

@app.get("/api/stats")
def api_get_stats(current_user: str = Depends(get_current_user)):
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    database.update_reservation_stats() # Call update_reservation_stats using the module prefix
    return {"msg": "Stats updated"}

# 后台任务：定期检查并过期预约、发送提醒、更新统计
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(periodic_expire_reservations())
    asyncio.create_task(periodic_send_reminders())
    asyncio.create_task(periodic_update_stats())
    asyncio.create_task(periodic_process_notifications())

async def periodic_expire_reservations():
    while True:
        database.expire_reservations() # Call expire_reservations using the module prefix
        await asyncio.sleep(60)  # 每分钟检查一次

async def periodic_send_reminders():
    while True:
        database.send_reminders() # Call send_reminders using the module prefix
        await asyncio.sleep(60)  # 每分钟检查一次

async def periodic_update_stats():
    while True:
        database.update_reservation_stats() # Call update_reservation_stats using the module prefix
        await asyncio.sleep(3600)  # 每小时更新一次

async def periodic_process_notifications():
    """定期处理待发送的通知"""
    while True:
        # Use the explicitly imported function
        process_notifications()
        await asyncio.sleep(60)  # 每分钟检查一次

class AreaCreate(BaseModel):
    name: str
    description: str
    floor: int

class SeatCreate(BaseModel):
    seat_number: str
    seat_type: SeatType
    has_power: bool = False
    has_computer: bool = False
    max_duration: int = 120

class SeatResponse(BaseModel):
    id: int
    seat_number: str
    seat_type: SeatType
    is_available: bool
    has_power: bool
    has_computer: bool
    max_duration: int

class AreaResponse(BaseModel):
    id: int
    name: str
    description: str
    floor: int
    seats: List[SeatResponse]

@app.post("/libraries/{library_id}/areas", response_model=AreaResponse)
async def create_area_endpoint(
    library_id: int,
    area: AreaCreate,
    current_user: str = Depends(get_current_user)
):
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    return database.create_area(library_id, area.name, area.description, area.floor) # Call create_area using the module prefix

@app.post("/areas/{area_id}/seats", response_model=SeatResponse)
async def create_seat_endpoint(
    area_id: int,
    seat: SeatCreate,
    current_user: str = Depends(get_current_user)
):
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    return database.create_seat(
        area_id,
        seat.seat_number,
        seat.seat_type,
        seat.has_power,
        seat.has_computer,
        seat.max_duration
    ) # Call create_seat using the module prefix

@app.get("/libraries/{library_id}/areas", response_model=List[AreaResponse])
async def get_areas(library_id: int):
    return database.get_library_areas(library_id) # Call get_library_areas using the module prefix

@app.get("/areas/{area_id}/seats", response_model=List[SeatResponse])
async def get_seats(area_id: int):
    return database.get_area_seats(area_id) # Call get_area_seats using the module prefix

@app.get("/areas/{area_id}/seats/type/{seat_type}", response_model=List[SeatResponse])
async def get_seats_by_type(area_id: int, seat_type: SeatType):
    return database.get_seat_by_type(area_id, seat_type) # Call get_seat_by_type using the module prefix

@app.get("/areas/{area_id}/seats/available/type/{seat_type}", response_model=List[SeatResponse])
async def get_available_seats_by_type(area_id: int, seat_type: SeatType):
    return database.get_available_seats_by_type(area_id, seat_type) # Call get_available_seats_by_type using the module prefix

@app.get("/areas/{area_id}/seats/facilities", response_model=List[SeatResponse])
async def get_seats_with_facilities(
    area_id: int,
    has_power: Optional[bool] = None,
    has_computer: Optional[bool] = None
):
    return database.get_seat_with_facilities(area_id, has_power, has_computer) # Call get_seat_with_facilities using the module prefix

@app.put("/seats/{seat_id}/status")
async def update_seat_availability(
    seat_id: int,
    is_available: bool,
    current_user: str = Depends(get_current_user)
):
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    seat = database.update_seat_status(seat_id, is_available) # Call update_seat_status using the module prefix
    if not seat:
        raise HTTPException(status_code=404, detail="Seat not found")
    return {"message": "Seat status updated successfully"}

class AreaUpdate(BaseModel):
    id: int
    name: Optional[str] = None
    description: Optional[str] = None
    floor: Optional[int] = None

class BatchAreaUpdate(BaseModel):
    areas: List[AreaUpdate]

@app.post("/admin/areas/{area_id}/import-seats")
async def import_seats(
    area_id: int,
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)
):
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # 保存上传的文件
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_file.flush()
        
        try:
            count = database.import_seats_from_csv(area_id, temp_file.name, current_user_id) # Call import_seats_from_csv using the module prefix, use user_id
            return {"message": f"Successfully imported {count} seats"}
        except Exception as e:
            database.log_system_action(
                database.LogLevel.ERROR, # Use database.LogLevel
                "seat_import",
                "import_seats_api",
                f"API seat import failed: {str(e)}",
                current_user_id
            )
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            os.unlink(temp_file.name)

@app.get("/admin/areas/{area_id}/export-seats")
async def export_seats(
    area_id: int,
    current_user: str = Depends(get_current_user)
):
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # 创建临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
        try:
            database.export_seats_to_csv(area_id, temp_file.name) # Call export_seats_to_csv using the module prefix
            return FileResponse(
                temp_file.name,
                media_type='text/csv',
                filename=f'seats_area_{area_id}.csv'
            )
        except Exception as e:
            database.log_system_action(
                database.LogLevel.ERROR, # Use database.LogLevel
                "seat_export",
                "export_seats_api",
                f"API seat export failed: {str(e)}",
                current_user_id
            )
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            # 文件会在发送后被删除
            os.unlink(temp_file.name)

@app.post("/admin/areas/batch-update")
async def batch_update_areas_endpoint(
    library_id: int,
    updates: BatchAreaUpdate,
    current_user: str = Depends(get_current_user)
):
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        count = database.batch_update_areas(library_id, [area.dict() for area in updates.areas], current_user_id) # Call batch_update_areas using the module prefix, use user_id
        return {"message": f"Successfully updated {count} areas"}
    except Exception as e:
        database.log_system_action(
            database.LogLevel.ERROR, # Use database.LogLevel
            "area_management",
            "batch_update_api",
            f"API batch update failed: {str(e)}",
            current_user_id
        )
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/admin/logs")
async def get_logs(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    level: Optional[LogLevel] = None,
    module: Optional[str] = None,
    current_user: str = Depends(get_current_user)
):
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    
    logs = database.get_system_logs(start_time, end_time, level, module) # Call get_system_logs using the module prefix
    return [
        {
            "timestamp": log.timestamp,
            "level": log.level.value,
            "module": log.module,
            "action": log.action,
            "details": log.details,
            "user_id": log.user_id,
            "ip_address": log.ip_address
        }
        for log in logs
    ]

@app.post("/admin/backup")
async def create_backup(current_user: str = Depends(get_current_user)):
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    
    if database.backup_database(backup_path): # Call backup_database using the module prefix
        database.log_system_action(
            database.LogLevel.INFO, # Use database.LogLevel
            "backup",
            "create_backup_api",
            f"Created backup at {backup_path}",
            current_user_id
        )
        return {"message": "Backup created successfully", "path": backup_path}
    raise HTTPException(status_code=500, detail="Failed to create backup")

@app.post("/admin/restore")
async def restore_from_backup(
    backup_path: str,
    current_user: str = Depends(get_current_user)
):
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if database.restore_database(backup_path): # Call restore_database using the module prefix
        database.log_system_action(
            database.LogLevel.INFO, # Use database.LogLevel
            "backup",
            "restore_backup_api",
            f"Restored from backup {backup_path}",
            current_user_id
        )
        return {"message": "Database restored successfully"}
    raise HTTPException(status_code=400, detail="Failed to restore database")

class UserCreate(BaseModel):
    username: str
    password: str
    email: EmailStr
    role: str = "user"

class PasswordReset(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class BlacklistCreate(BaseModel):
    user_id: int
    reason: str
    end_date: Optional[datetime] = None

class PointsUpdate(BaseModel):
    user_id: int
    points: int
    reason: str

@app.post("/users/register", response_model=dict)
async def register_user(user: UserCreate):
    """注册新用户"""
    try:
        new_user = database.create_user_with_verification(
            username=user.username,
            password=user.password,
            email=user.email,
            role=user.role
        ) # Call create_user_with_verification using the module prefix
        return {
            "message": "Registration successful. Please check your email for verification.",
            "user_id": new_user.id
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/users/verify/{token}")
async def verify_email(token: str):
    """验证用户邮箱"""
    if database.verify_user_email(token): # Call verify_user_email using the module prefix
        return {"message": "Email verified successfully"}
    raise HTTPException(status_code=400, detail="Invalid or expired verification token")

@app.post("/users/reset-password")
async def request_password_reset(reset: PasswordReset):
    """请求密码重置"""
    token = database.create_password_reset_token(reset.email) # Call create_password_reset_token using the module prefix
    if token:
        # TODO: 发送重置密码邮件
        return {"message": "Password reset instructions sent to your email"}
    raise HTTPException(status_code=404, detail="User not found")

@app.post("/users/reset-password/confirm")
async def confirm_password_reset(reset: PasswordResetConfirm):
    """确认密码重置"""
    if database.reset_password(reset.token, reset.new_password): # Call reset_password using the module prefix
        return {"message": "Password reset successful"}
    raise HTTPException(status_code=400, detail="Invalid or expired reset token")

@app.post("/admin/blacklist", response_model=dict)
async def blacklist_user(
    blacklist: BlacklistCreate,
    current_user: str = Depends(get_current_user) # current_user is str
):
    current_user_id = int(current_user)
    # Note: check_admin function expects user_id (int), not user object or dict
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        # Note: add_to_blacklist expects admin_id (int), not user object or dict
        result = database.add_to_blacklist(
            user_id=blacklist.user_id,
            reason=blacklist.reason,
            end_date=blacklist.end_date,
            admin_id=current_user_id # Pass integer admin_id
        ) # Call add_to_blacklist using the module prefix
        return {"message": "User added to blacklist successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/admin/blacklist/{user_id}")
async def remove_blacklist(
    user_id: int,
    current_user: str = Depends(get_current_user) # current_user is str
):
    """将用户从黑名单中移除"""
    current_user_id = int(current_user)
    # Note: check_admin function expects user_id (int), not user object or dict
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Note: remove_from_blacklist expects admin_id (int), not user object or dict
    if database.remove_from_blacklist(user_id, current_user_id): # Call remove_from_blacklist using the module prefix, pass integer admin_id
        return {"message": "User removed from blacklist successfully"}
    raise HTTPException(status_code=404, detail="User not found in blacklist")

@app.get("/users/{user_id}/blacklist")
async def check_blacklist_status(
    user_id: int,
    current_user: str = Depends(get_current_user) # current_user is str
):
    """检查用户黑名单状态"""
    current_user_id = int(current_user)
    # Note: check_admin function expects user_id (int), not user object or dict
    if current_user_id != user_id and not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    
    blacklist = database.get_blacklist_status(user_id) # Call get_blacklist_status using the module prefix
    if blacklist:
        return {
            "is_blacklisted": True,
            "reason": blacklist.reason,
            "end_date": blacklist.end_date
        }
    return {"is_blacklisted": False}

@app.post("/admin/points", response_model=dict)
async def update_points(
    points_update: PointsUpdate,
    current_user: str = Depends(get_current_user) # current_user is str
):
    """更新用户积分"""
    current_user_id = int(current_user)
    # Note: check_admin function expects user_id (int), not user object or dict
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if database.update_user_points(
        user_id=points_update.user_id,
        points=points_update.points,
        reason=points_update.reason
    ): # Call update_user_points using the module prefix
        return {"message": "Points updated successfully"}
    raise HTTPException(status_code=404, detail="User not found")

@app.get("/users/{user_id}/points/history")
async def get_points_history(
    user_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: str = Depends(get_current_user) # current_user is str
):
    """获取用户积分历史"""
    current_user_id = int(current_user)
    # Note: check_admin function expects user_id (int), not user object or dict
    if current_user_id != user_id and not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    
    history = database.get_user_points_history(user_id, start_date, end_date) # Call get_user_points_history using the module prefix
    return [
        {
            "points": record.points,
            "reason": record.reason,
            "created_at": record.created_at
        }
        for record in history
    ]

class NotificationTemplateCreate(BaseModel):
    name: str
    type: NotificationType
    title_template: str
    content_template: str

class NotificationCreate(BaseModel):
    user_id: int
    type: NotificationType
    title: str
    content: str
    metadata: Optional[Dict] = None

@app.post("/admin/notification-templates", response_model=dict)
async def create_template(
    template: NotificationTemplateCreate,
    current_user: str = Depends(get_current_user)
):
    """创建通知模板"""
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        template = database.create_notification_template(
            name=template.name,
            type=template.type,
            title_template=template.title_template,
            content_template=template.content_template
        ) # Call create_notification_template using the module prefix
        return {
            "message": "Template created successfully",
            "template_id": template.id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/admin/notification-templates/{name}")
async def get_template(
    name: str,
    current_user: str = Depends(get_current_user)
):
    """获取通知模板"""
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    
    template = database.get_notification_template(name) # Call get_notification_template using the module prefix
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {
        "id": template.id,
        "name": template.name,
        "type": template.type.value,
        "title_template": template.title_template,
        "content_template": template.content_template,
        "is_active": template.is_active,
        "created_at": template.created_at,
        "updated_at": template.updated_at
    }

@app.post("/notifications", response_model=dict)
async def send_notification(
    notification: NotificationCreate,
    current_user: str = Depends(get_current_user)
):
    """发送通知"""
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        notification = database.create_notification(
            user_id=notification.user_id,
            type=notification.type,
            title=notification.title,
            content=notification.content,
            metadata=notification.metadata
        ) # Call create_notification using the module prefix
        return {
            "message": "Notification created successfully",
            "notification_id": notification.id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/admin/notifications/pending")
async def get_pending_notifications_list(
    current_user: str = Depends(get_current_user)
):
    """获取待发送的通知列表"""
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="Not authorized")
    
    notifications = database.get_pending_notifications() # Call get_pending_notifications using the module prefix
    return [
        {
            "id": notification.id,
            "user_id": notification.user_id,
            "type": notification.type.value,
            "title": notification.title,
            "content": notification.content,
            "created_at": notification.created_at,
            "extra_data": json.loads(notification.extra_data) if notification.extra_data else None # Use extra_data
        }
        for notification in notifications
    ]

# 预约提醒邮件模板 - This part seems incomplete and might cause issues if not fully implemented or removed.
# template = {
#     "name": "reservation_reminder",
#     "type": "email",
#     "title_template": "预约提醒：您的座位预约即将开始",
#     "content_template": """
#     <h1>预约提醒</h1>
#     <p>尊敬的{username}：</p>
#     <p>您的座位预约将在{start_time}开始，请准时到达。</p>
#     <p>座位信息：{seat_number}</p>
#     <p>图书馆：{library_name}</p>
#     """
# }

class ReportCreate(BaseModel):
    name: str
    type: ReportType
    format: ReportFormat
    parameters: dict

class SystemConfigUpdate(BaseModel):
    value: Any # Use Any for flexible config value type
    description: str

class LibraryScheduleUpdate(BaseModel):
    schedules: List[Dict]

class ReservationRuleUpdate(BaseModel):
    max_reservations_per_day: int
    max_reservations_per_week: int
    min_reservation_duration: int
    max_reservation_duration: int
    allow_same_day_reservation: bool
    allow_future_reservation: bool
    max_future_days: int
    cancellation_deadline: int
    no_show_penalty: int
    blacklist_threshold: int

# Pydantic models for responses (using orm_mode)
class ReportResponse(BaseModel):
    id: int
    name: str
    type: database.ReportType
    format: database.ReportFormat
    parameters: Dict
    created_by: int
    created_at: datetime
    file_path: Optional[str] = None
    status: str
    error_message: Optional[str] = None

    class Config:
        orm_mode = True

@app.post("/reports", response_model=ReportResponse)
async def create_report_endpoint(
    report: ReportCreate,
    current_user: str = Depends(get_current_user)
):
    """创建报告任务"""
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="只有管理员可以创建报告")
    
    try:
        new_report = database.create_report(
            name=report.name,
            type=report.type,
            format=report.format,
            parameters=report.parameters,
            created_by=current_user_id # Pass integer user_id
        ) # Call create_report using the module prefix
        return new_report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reports/{report_id}", response_model=ReportResponse)
async def get_report_endpoint(
    report_id: int,
    current_user: str = Depends(get_current_user)
):
    """获取报告信息"""
    current_user_id = int(current_user)
    report = database.get_report(report_id) # Call get_report using the module prefix
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    
    # Compare integer user IDs
    if not database.check_admin(current_user_id) and report.created_by != current_user_id:
        raise HTTPException(status_code=403, detail="无权访问此报告")
    
    return report

@app.get("/reports", response_model=List[ReportResponse])
async def get_user_reports_endpoint(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: str = Depends(get_current_user)
):
    """获取用户的报告列表"""
    current_user_id = int(current_user)
    reports = database.get_user_reports(
        user_id=current_user_id, # Pass integer user_id
        start_date=start_date,
        end_date=end_date
    ) # Call get_user_reports using the module prefix
    return reports

@app.get("/reports/{report_id}/download")
async def download_report(
    report_id: int,
    current_user: str = Depends(get_current_user)
):
    """下载报告文件"""
    current_user_id = int(current_user)
    report = database.get_report(report_id) # Call get_report using the module prefix
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    
    # Compare integer user IDs
    if not database.check_admin(current_user_id) and report.created_by != current_user_id:
        raise HTTPException(status_code=403, detail="无权访问此报告")
    
    if not report.file_path or not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="报告文件不存在")
    
    return FileResponse(
        report.file_path,
        filename=os.path.basename(report.file_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.get("/reports/{report_id}/chart")
async def get_report_chart(
    report_id: int,
    current_user: str = Depends(get_current_user)
):
    """获取报告图表数据"""
    current_user_id = int(current_user)
    report = database.get_report(report_id) # Call get_report using the module prefix
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    
    # Compare integer user IDs
    if not database.check_admin(current_user_id) and report.created_by != current_user_id:
        raise HTTPException(status_code=403, detail="无权访问此报告")
    
    try:
        chart_data = database.generate_chart_data(report.type, report.parameters) # Call generate_chart_data using the module prefix
        return chart_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/system/config/{key}")
async def get_system_config_endpoint(
    key: str,
    current_user: str = Depends(get_current_user)
):
    """获取系统配置"""
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="只有管理员可以访问系统配置")
    
    config = database.get_system_config(key) # Call get_system_config using the module prefix
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    return config

@app.put("/system/config/{key}")
async def update_system_config_endpoint(
    key: str,
    config_update: SystemConfigUpdate,
    current_user: str = Depends(get_current_user)
):
    """更新系统配置"""
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="只有管理员可以更新系统配置")
    
    try:
        config = database.update_system_config(
            key=key,
            value=config_update.value,
            description=config_update.description,
            updated_by=current_user_id # Pass integer user_id
        ) # Call update_system_config using the module prefix
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/libraries/{library_id}/schedule")
async def get_library_schedule_endpoint(
    library_id: int,
    date: Optional[datetime] = None,
    current_user: str = Depends(get_current_user)
):
    """获取图书馆开放时间"""
    # No admin check here based on previous code, assuming public access
    schedules = database.get_library_schedule(library_id, date) # Call get_library_schedule using the module prefix
    return schedules

@app.put("/libraries/{library_id}/schedule")
async def update_library_schedule_endpoint(
    library_id: int,
    schedule_update: LibraryScheduleUpdate,
    current_user: str = Depends(get_current_user)
):
    """更新图书馆开放时间"""
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="只有管理员可以更新开放时间")
    
    try:
        schedules = database.update_library_schedule(
            library_id=library_id,
            schedules=schedule_update.schedules,
            created_by=current_user_id # Pass integer user_id
        ) # Call update_library_schedule using the module prefix
        return schedules
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/libraries/{library_id}/reservation-rules")
async def get_reservation_rules_endpoint(
    library_id: int,
    current_user: str = Depends(get_current_user)
):
    """获取预约规则"""
    # No admin check here based on previous code, assuming public access
    rules = database.get_reservation_rules(library_id) # Call get_reservation_rules using the module prefix
    if not rules:
        raise HTTPException(status_code=404, detail="预约规则不存在")
    
    return rules

@app.put("/libraries/{library_id}/reservation-rules")
async def update_reservation_rules_endpoint(
    library_id: int,
    rules_update: ReservationRuleUpdate,
    current_user: str = Depends(get_current_user)
):
    """更新预约规则"""
    current_user_id = int(current_user)
    if not database.check_admin(current_user_id): # Call check_admin using the module prefix
        raise HTTPException(status_code=403, detail="只有管理员可以更新预约规则")
    
    try:
        rules = database.update_reservation_rules(
            library_id=library_id,
            rules=rules_update.dict(),
            created_by=current_user_id # Pass integer user_id
        ) # Call update_reservation_rules using the module prefix
        return rules
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 