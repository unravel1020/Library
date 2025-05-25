from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Enum, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()

class SeatType(enum.Enum):
    REGULAR = "regular"  # 普通座位
    COMPUTER = "computer"  # 电脑座位
    DISCUSSION = "discussion"  # 讨论区
    QUIET = "quiet"  # 安静区
    GROUP = "group"  # 小组讨论区

class ReservationStatus(enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

class UserStatus(enum.Enum):
    ACTIVE = "active"
    PENDING = "pending"  # 等待邮箱验证
    BLOCKED = "blocked"  # 被加入黑名单
    DISABLED = "disabled"  # 账号被禁用

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    email = Column(String, unique=True, index=True)
    role = Column(String)  # admin or user
    status = Column(Enum(UserStatus), default=UserStatus.PENDING)
    points = Column(Integer, default=0)  # 用户积分
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    verification_token = Column(String, nullable=True)  # 邮箱验证token
    reset_token = Column(String, nullable=True)  # 密码重置token
    reset_token_expires = Column(DateTime, nullable=True)  # 重置token过期时间

class Library(Base):
    __tablename__ = "libraries"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    location = Column(String)
    total_seats = Column(Integer)
    available_seats = Column(Integer)
    occupied_seats = Column(Integer)
    reserved_seats = Column(Integer)
    areas = relationship("Area", back_populates="library")

class Area(Base):
    __tablename__ = "areas"
    id = Column(Integer, primary_key=True, index=True)
    library_id = Column(Integer, ForeignKey("libraries.id"))
    name = Column(String)
    description = Column(String)
    floor = Column(Integer)
    seats = relationship("Seat", back_populates="area")
    library = relationship("Library", back_populates="areas")

class Seat(Base):
    __tablename__ = "seats"
    id = Column(Integer, primary_key=True, index=True)
    area_id = Column(Integer, ForeignKey("areas.id"))
    seat_number = Column(String)
    seat_type = Column(Enum(SeatType))
    is_available = Column(Boolean, default=True)
    has_power = Column(Boolean, default=False)
    has_computer = Column(Boolean, default=False)
    max_duration = Column(Integer)  # 最大使用时长（分钟）
    area = relationship("Area", back_populates="seats")
    reservations = relationship("Reservation", back_populates="seat")

class Reservation(Base):
    __tablename__ = "reservations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    seat_id = Column(Integer, ForeignKey("seats.id"))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    status = Column(Enum(ReservationStatus), default=ReservationStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    seat = relationship("Seat", back_populates="reservations")

class Reminder(Base):
    __tablename__ = "reminders"
    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    reminder_time = Column(DateTime)
    sent = Column(Boolean, default=False)

class ReservationStats(Base):
    __tablename__ = "reservation_stats"
    id = Column(Integer, primary_key=True, index=True)
    library_id = Column(Integer, ForeignKey("libraries.id"))
    date = Column(DateTime)
    total_reservations = Column(Integer, default=0)
    active_reservations = Column(Integer, default=0)
    cancelled_reservations = Column(Integer, default=0)
    expired_reservations = Column(Integer, default=0)

class LogLevel(enum.Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

class SystemLog(Base):
    __tablename__ = "system_logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    level = Column(Enum(LogLevel))
    module = Column(String)  # 模块名称
    action = Column(String)  # 操作类型
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    details = Column(Text)  # 详细信息
    ip_address = Column(String, nullable=True)  # 操作IP

class Blacklist(Base):
    __tablename__ = "blacklist"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    reason = Column(Text)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)  # 如果为null则表示永久封禁
    created_by = Column(Integer, ForeignKey("users.id"))  # 执行封禁的管理员
    created_at = Column(DateTime, default=datetime.utcnow)

class PointsHistory(Base):
    __tablename__ = "points_history"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    points = Column(Integer)  # 正数表示增加，负数表示减少
    reason = Column(String)  # 积分变动原因
    created_at = Column(DateTime, default=datetime.utcnow)

class NotificationType(enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    SYSTEM = "system"

class NotificationStatus(enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(Enum(NotificationType))
    title = Column(String)
    content = Column(Text)
    status = Column(Enum(NotificationStatus), default=NotificationStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    extra_data = Column(Text, nullable=True)  # Renamed from metadata

class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    type = Column(Enum(NotificationType))
    title_template = Column(String)
    content_template = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ReportType(enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"

class ReportFormat(enum.Enum):
    EXCEL = "excel"
    PDF = "pdf"
    CSV = "csv"

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    type = Column(Enum(ReportType))
    format = Column(Enum(ReportFormat))
    parameters = Column(JSON)  # 存储报告参数（如时间范围、筛选条件等）
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    file_path = Column(String, nullable=True)  # 存储生成的文件路径
    status = Column(String, default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)

class SystemConfig(Base):
    __tablename__ = "system_configs"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True)
    value = Column(JSON)
    description = Column(Text)
    updated_by = Column(Integer, ForeignKey("users.id"))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class LibrarySchedule(Base):
    __tablename__ = "library_schedules"
    id = Column(Integer, primary_key=True, index=True)
    library_id = Column(Integer, ForeignKey("libraries.id"))
    day_of_week = Column(Integer)  # 0-6 表示周一到周日
    open_time = Column(String)  # 格式：HH:MM
    close_time = Column(String)  # 格式：HH:MM
    is_closed = Column(Boolean, default=False)
    special_date = Column(DateTime, nullable=True)  # 特殊日期（如节假日）
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ReservationRule(Base):
    __tablename__ = "reservation_rules"
    id = Column(Integer, primary_key=True, index=True)
    library_id = Column(Integer, ForeignKey("libraries.id"))
    max_duration = Column(Integer)  # 最大预约时长（分钟）
    min_duration = Column(Integer)  # 最小预约时长（分钟）
    max_advance_days = Column(Integer)  # 最大提前预约天数
    max_daily_reservations = Column(Integer)  # 每日最大预约次数
    max_concurrent_reservations = Column(Integer)  # 最大同时预约数
    cancellation_deadline = Column(Integer)  # 取消预约截止时间（分钟）
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) 