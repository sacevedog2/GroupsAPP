import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.db.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class RoleEnum(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"

class Group(Base):
    __tablename__ = "groups"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    settings = Column(JSON, nullable=True, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    channels = relationship("Channel", back_populates="group", cascade="all, delete-orphan")

class Channel(Base):
    __tablename__ = "channels"

    id = Column(String, primary_key=True, default=generate_uuid)
    group_id = Column(String, ForeignKey("groups.id"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    group = relationship("Group", back_populates="channels")

class GroupMember(Base):
    __tablename__ = "group_members"

    group_id = Column(String, ForeignKey("groups.id"), primary_key=True)
    user_id = Column(String, primary_key=True)
    role = Column(String, nullable=False, default=RoleEnum.MEMBER.value)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    group = relationship("Group", back_populates="members")

class Contact(Base):
    __tablename__ = "contacts"

    owner_id = Column(String, primary_key=True)
    contact_user_id = Column(String, primary_key=True)
    alias = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
