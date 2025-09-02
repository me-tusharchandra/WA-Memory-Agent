import os
import hashlib

from typing import Optional
from datetime import datetime
from sqlalchemy.sql import func
from app.config import settings
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON


engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    whatsapp_id = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    interactions = relationship("Interaction", back_populates="user")
    memories = relationship("Memory", back_populates="user")


class Media(Base):
    __tablename__ = "media"
    
    id = Column(Integer, primary_key=True, index=True)
    content_hash = Column(String, unique=True, index=True, nullable=False)
    media_type = Column(String, nullable=False)  # image, audio, video
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String)
    media_metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    interactions = relationship("Interaction", back_populates="media")


class Interaction(Base):
    __tablename__ = "interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    twilio_message_sid = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    interaction_type = Column(String, nullable=False)  # text, image, audio, command
    content = Column(Text)
    media_id = Column(Integer, ForeignKey("media.id"))
    transcript = Column(Text)  # For audio messages
    interaction_metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="interactions")
    media = relationship("Media", back_populates="interactions")
    memories = relationship("Memory", back_populates="interaction")


class Memory(Base):
    __tablename__ = "memories"
    
    id = Column(Integer, primary_key=True, index=True)
    mem0_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    interaction_id = Column(Integer, ForeignKey("interactions.id"), nullable=False)
    content = Column(Text, nullable=False)
    memory_type = Column(String, nullable=False)  # text, image, audio
    tags = Column(JSON)  # Store tags/labels as JSON array
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="memories")
    interaction = relationship("Interaction", back_populates="memories")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    Base.metadata.create_all(bind=engine)


def get_content_hash(content: bytes) -> str:
    """Generate a content hash for deduplication"""
    return hashlib.sha256(content).hexdigest()


def ensure_media_directory():
    """Ensure the media directory exists"""
    media_dir = "media"
    if not os.path.exists(media_dir):
        os.makedirs(media_dir)
    return media_dir
