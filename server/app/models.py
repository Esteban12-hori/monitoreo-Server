from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, Table
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

# Tabla de asociación para User <-> Server
user_server_link = Table('user_server_link', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('server_id', Integer, ForeignKey('servers.id'), primary_key=True)
)


class Server(Base):
    __tablename__ = "servers"
    id = Column(Integer, primary_key=True)
    server_id = Column(String(255), unique=True, index=True, nullable=False)
    token = Column(String(255), nullable=False)
    report_interval = Column(Integer, default=2400) # Segundos
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    group_name = Column(String(255), nullable=True, index=True) # Nuevo campo


class AlertRule(Base):
    __tablename__ = "alert_rules"
    id = Column(Integer, primary_key=True)
    alert_type = Column(String(50), nullable=False) # 'cpu', 'memory', 'disk', 'offline'
    server_scope = Column(String(20), nullable=False) # 'global', 'server', 'group'
    target_id = Column(String(255), nullable=True) # server_id o group_name
    emails = Column(Text, nullable=False) # Lista de emails en JSON (e.g. ["a@b.com", "c@d.com"])
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
    receive_alerts = Column(Boolean, default=False) # Nuevo campo
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relación Many-to-Many con Server
    servers = relationship("Server", secondary=user_server_link, backref="assigned_users")


class UserSession(Base):
    __tablename__ = "sessions"
    token = Column(String(255), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User")
