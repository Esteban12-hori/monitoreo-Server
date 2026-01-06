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

class UserResponseSchema(BaseModel):
    id: int
    email: str
    name: Optional[str]
    is_admin: bool
    created_at: Optional[datetime]

    class Config:
        from_attributes = True

class ChangePasswordSchema(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)

class ServerConfigUpdateSchema(BaseModel):
    report_interval: int = Field(..., ge=5, le=86400) # 5s to 24h
