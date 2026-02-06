from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime


class MemorySchema(BaseModel):
    total: float
    used: float
    free: float
    cache: float


class CpuSchema(BaseModel):
    total: float
    per_core: List[float]


class DiskSchema(BaseModel):
    total: float
    used: float
    free: float
    percent: float


class DockerContainerSchema(BaseModel):
    name: str
    cpu: Optional[float] = None
    mem: Optional[float] = None


class DockerSchema(BaseModel):
    running_containers: int
    containers: List[DockerContainerSchema] = []


class MetricsIngestSchema(BaseModel):
    server_id: str
    memory: MemorySchema
    cpu: CpuSchema
    disk: DiskSchema
    docker: DockerSchema
    timestamp: Optional[str] = None


class RegisterServerSchema(BaseModel):
    server_id: str = Field(..., min_length=1)
    token: str = Field(..., min_length=8)


class AlertConfigSchema(BaseModel):
    cpu_total_percent: float
    memory_used_percent: float
    disk_used_percent: float

class LoginSchema(BaseModel):
    email: str
    password: str

class UserCreateSchema(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    name: Optional[str] = None
    is_admin: bool = False
    receive_alerts: bool = False
    can_view_data_monitoring: bool = False

class UserUpdateSchema(BaseModel):
    name: Optional[str] = None
    is_admin: Optional[bool] = None
    receive_alerts: Optional[bool] = None
    can_view_data_monitoring: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6)

class UserResponseSchema(BaseModel):
    id: int
    email: str
    name: Optional[str]
    is_admin: bool
    receive_alerts: bool
    can_view_data_monitoring: bool = False
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class DataMonitoringSchema(BaseModel):
    app: str
    cash_register_number: Optional[int] = Field(None, alias="cashRegisterNumber")
    user_name: str = Field(..., alias="userName")
    flow: str
    patent: Optional[str] = None
    vehicle_type: Optional[str] = Field(None, alias="vehicleType")
    product: Optional[str] = None
    created_at_client: str = Field(..., alias="createdAt")
    entity_id: str = Field(..., alias="entityId")
    working_day: str = Field(..., alias="workingDay")

    class Config:
        populate_by_name = True

class DataMonitoringResponseSchema(DataMonitoringSchema):
    id: int
    received_at: datetime

    class Config:
        from_attributes = True

class ServerAssignmentItem(BaseModel):
    server_id: str
    receive_alerts: bool = True

class ServerAssignmentSchema(BaseModel):
    assignments: List[ServerAssignmentItem]

class UserServerAssignmentResponse(BaseModel):
    server_id: str
    receive_alerts: bool

class ChangePasswordSchema(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)

class ServerConfigUpdateSchema(BaseModel):
    report_interval: int = Field(..., ge=5, le=86400) # 5s to 24h


class ServerDataMonitoringUpdateSchema(BaseModel):
    enabled: bool


class AlertRecipientSchema(BaseModel):
    id: int
    email: str
    name: Optional[str]
    recipient_type: Optional[str] = "OTROS"
    created_at: Optional[datetime]

    class Config:
        from_attributes = True

class AlertRecipientCreateSchema(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    recipient_type: Optional[str] = "OTROS"


class AlertRuleBase(BaseModel):
    alert_type: str = Field(..., pattern="^(cpu|memory|disk|offline)$")
    server_scope: str = Field(..., pattern="^(global|server|group)$")
    target_id: Optional[str] = None
    emails: List[EmailStr]

class AlertRuleCreate(AlertRuleBase):
    pass

class AlertRuleResponse(AlertRuleBase):
    id: int
    created_at: Optional[datetime]

    class Config:
        from_attributes = True

class ServerUpdateGroupSchema(BaseModel):
    group_name: Optional[str]


class ServerThresholdBase(BaseModel):
    cpu_threshold: Optional[float] = Field(None, ge=0.1, le=100.0)
    memory_threshold: Optional[float] = Field(None, ge=0.1, le=100.0)
    disk_threshold: Optional[float] = Field(None, ge=0.1, le=100.0)

class ServerThresholdUpdate(ServerThresholdBase):
    pass

class ServerThresholdImport(ServerThresholdBase):
    server_id: str

class ServerThresholdResponse(ServerThresholdBase):
    server_id: str
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class AuditLogResponse(BaseModel):
    id: int
    action: str
    target_type: str
    target_id: Optional[str]
    changes: Optional[str]
    user_email: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True
