from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, Table
from sqlalchemy.orm import declarative_base, relationship, backref
from sqlalchemy.sql import func

Base = declarative_base()

# Tabla de asociación para User <-> Server (Modelo explícito para campos extra)
class UserServerLink(Base):
    __tablename__ = 'user_server_link'
    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    server_id = Column(Integer, ForeignKey('servers.id'), primary_key=True)
    receive_alerts = Column(Boolean, default=True) # Controla si recibe alertas de este servidor específico

    # Relationships
    user = relationship("User", back_populates="server_links")
    server = relationship("Server", back_populates="user_links")


class Server(Base):
    __tablename__ = "servers"
    id = Column(Integer, primary_key=True)
    server_id = Column(String(255), unique=True, index=True, nullable=False)
    token = Column(String(255), nullable=False)
    report_interval = Column(Integer, default=2400) # Segundos
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    group_name = Column(String(255), nullable=True, index=True) # Nuevo campo

    # Relación a través de UserServerLink
    user_links = relationship("UserServerLink", back_populates="server", cascade="all, delete-orphan")
    # Helper para obtener usuarios directamente (read-only recomendado para evitar conflictos)
    assigned_users = relationship("User", secondary="user_server_link", viewonly=True)


class DataMonitoringServerConfig(Base):
    __tablename__ = "data_monitoring_server_config"

    id = Column(Integer, primary_key=True)
    server_id = Column(String(255), ForeignKey("servers.server_id"), unique=True, nullable=False)
    enabled = Column(Boolean, default=False)


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
    recipient_type = Column(String(50), default="OTROS") # VS, SV, OTROS
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
    server_links = relationship("UserServerLink", back_populates="user", cascade="all, delete-orphan")
    servers = relationship("Server", secondary="user_server_link", viewonly=True)


class UserSession(Base):
    __tablename__ = "sessions"
    token = Column(String(255), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User")


class ServerThreshold(Base):
    __tablename__ = "server_thresholds"
    id = Column(Integer, primary_key=True)
    server_id = Column(String(255), ForeignKey('servers.server_id'), unique=True, nullable=False)
    
    cpu_threshold = Column(Float, nullable=True)     # %
    memory_threshold = Column(Float, nullable=True)  # %
    disk_threshold = Column(Float, nullable=True)    # %
    
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationship to Server
    server = relationship("Server", backref=backref("threshold", uselist=False, cascade="all, delete-orphan"))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    action = Column(String(255), nullable=False)
    target_type = Column(String(50), nullable=False) # e.g. 'threshold', 'user'
    target_id = Column(String(255), nullable=True)
    changes = Column(Text, nullable=True) # JSON details
    user_email = Column(String(255), nullable=True) # Who did it
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class DataMonitoring(Base):
    __tablename__ = "data_monitoring"

    id = Column(Integer, primary_key=True)
    app = Column(String(100), nullable=False)
    cash_register_number = Column(Integer, nullable=True)
    user_name = Column(String(255), nullable=False)
    flow = Column(String(100), nullable=False)
    patent = Column(String(50), nullable=True)
    vehicle_type = Column(String(50), nullable=True)
    product = Column(String(100), nullable=True)
    created_at_client = Column(String(100), nullable=False)
    entity_id = Column(String(100), nullable=False)
    working_day = Column(String(100), nullable=False)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
