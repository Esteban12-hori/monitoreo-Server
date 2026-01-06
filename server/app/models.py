from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Server(Base):
    __tablename__ = "servers"
    id = Column(Integer, primary_key=True)
    server_id = Column(String(255), unique=True, index=True, nullable=False)
    token = Column(String(255), nullable=False)
    report_interval = Column(Integer, default=2400) # Segundos
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Metric(Base):
    __tablename__ = "metrics"
    id = Column(Integer, primary_key=True)
    server_id = Column(String(255), index=True, nullable=False)
    ts = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    mem_total = Column(Float)
    mem_used = Column(Float)
    mem_free = Column(Float)
    mem_cache = Column(Float)

    cpu_total = Column(Float)
    cpu_per_core = Column(Text)  # JSON serializado

    disk_total = Column(Float)
    disk_used = Column(Float)
    disk_free = Column(Float)
    disk_percent = Column(Float)

    docker_running = Column(Integer)
    docker_containers = Column(Text)  # JSON serializado


class AlertConfig(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    cpu_total_percent = Column(Float)
    memory_used_percent = Column(Float)
    disk_used_percent = Column(Float)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AlertRecipient(Base):
    __tablename__ = "alert_recipients"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())



class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserSession(Base):
    __tablename__ = "sessions"
    token = Column(String(255), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User")
