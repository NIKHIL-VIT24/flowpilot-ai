from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; name: str; email: str; notifications: bool

class CampaignIn(BaseModel):
    name: str; channel: str = "Email"; status: str = "Draft"; audience: str = "All contacts"; budget: float = 0
class CampaignUpdate(BaseModel):
    name: str | None = None; channel: str | None = None; status: str | None = None; audience: str | None = None; budget: float | None = None
    impressions: int | None = None; clicks: int | None = None; conversions: int | None = None; spend: float | None = None; revenue: float | None = None
class CampaignOut(CampaignIn):
    model_config = ConfigDict(from_attributes=True)
    id: int; impressions: int; clicks: int; conversions: int; spend: float; revenue: float; created_at: datetime; updated_at: datetime

class WorkflowIn(BaseModel):
    name: str; trigger: str; actions: list[str] = []
class WorkflowUpdate(BaseModel):
    active: bool | None = None; name: str | None = None; trigger: str | None = None; actions: list[str] | None = None
class WorkflowOut(WorkflowIn):
    model_config = ConfigDict(from_attributes=True)
    id: int; active: bool; created_at: datetime

class ContactIn(BaseModel):
    name: str; email: EmailStr; source: str = "Manual"; status: str = "Active"
class ContactOut(ContactIn):
    model_config = ConfigDict(from_attributes=True)
    id: int; created_at: datetime

class IntegrationIn(BaseModel):
    provider: str
    config: dict = {}
class IntegrationOut(BaseModel):
    provider: str; connected: bool; updated_at: datetime | None = None

class DraftIn(BaseModel):
    title: str; channel: str = "Email"; body: str
class DraftOut(DraftIn):
    model_config = ConfigDict(from_attributes=True)
    id: int; created_at: datetime

class AIIn(BaseModel):
    prompt: str = Field(min_length=3)
    channel: str = "Email"

class SettingsIn(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    notifications: bool | None = None
