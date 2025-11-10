from pydantic import BaseModel, Field
from typing import List, Optional


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