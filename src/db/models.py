"""
src/db/models.py — SQLAlchemy ORM Models
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, JSON, BigInteger, text
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class Conversation(Base):
    __tablename__ = 'conversations'
    id = Column(Integer, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    role = Column(String, nullable=False)
    content = Column(String, nullable=False)
    tokens = Column(Integer)
    summarized = Column(Boolean, default=False)
    summary_id = Column(Integer)

class Summary(Base):
    __tablename__ = 'summaries'
    id = Column(Integer, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    content = Column(String, nullable=False)
    tokens = Column(Integer)
    messages_start = Column(Integer)
    messages_end = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Fact(Base):
    __tablename__ = 'facts'
    id = Column(Integer, primary_key=True)
    category = Column(String, nullable=False, index=True)
    key = Column(String, nullable=False, index=True)
    value = Column(String, nullable=False)
    context = Column(String)
    confidence = Column(Float, default=1.0)
    source_session = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    access_count = Column(Integer, default=0)
    superseded_by = Column(Integer, ForeignKey('facts.id'))

class MemoryEmbedding(Base):
    __tablename__ = 'memory_embeddings'
    id = Column(Integer, primary_key=True)
    content = Column(String, nullable=False)
    embedding = Column(Vector(384))
    metadata_json = Column("metadata", JSON) # metadata is a reserved word sometimes, but column is 'metadata'
    type = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TaskModel(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    type = Column(String, nullable=False)
    status = Column(String, nullable=False, index=True)
    priority = Column(Integer, default=2)
    input_data = Column(JSON)
    output_data = Column(JSON)
    output_text = Column(String)
    output_media = Column(JSON)
    agent_used = Column(String)
    model_used = Column(String)
    llm_calls = Column(Integer, default=0)
    tokens_used = Column(Integer, default=0)
    error_message = Column(String)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    checkpoint = Column(JSON)

class Approval(Base):
    __tablename__ = 'approvals'
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('tasks.id'), index=True)
    action_type = Column(String, nullable=False)
    description = Column(String)
    preview_data = Column(JSON)
    status = Column(String, default='pending', index=True)
    telegram_msg_id = Column(BigInteger)
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    responded_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))

class ScheduledJob(Base):
    __tablename__ = 'scheduled_jobs'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    schedule_type = Column(String, nullable=False)
    schedule_value = Column(String, nullable=False)
    task_template = Column(JSON, nullable=False)
    approval_mode = Column(String, default='each_time')
    enabled = Column(Boolean, default=True, index=True)
    last_run = Column(DateTime(timezone=True))
    next_run = Column(DateTime(timezone=True), index=True)
    run_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Cache(Base):
    __tablename__ = 'cache'
    id = Column(Integer, primary_key=True)
    prompt_hash = Column(String, unique=True, nullable=False, index=True)
    prompt_preview = Column(String)
    response = Column(String, nullable=False)
    model_used = Column(String)
    tokens_saved = Column(Integer)
    hit_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), index=True)
    last_hit = Column(DateTime(timezone=True))

class SystemState(Base):
    __tablename__ = 'system_state'
    key = Column(String, primary_key=True)
    value = Column(String)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class OutputHistory(Base):
    __tablename__ = 'output_history'
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('tasks.id'), index=True)
    sequence_number = Column(Integer, default=1)
    output_envelope = Column(JSON)
    rendered_for = Column(String)
    telegram_msg_id = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class OutputFile(Base):
    __tablename__ = 'output_files'
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('tasks.id'), index=True)
    file_type = Column(String)
    storage_path = Column(String)
    file_size = Column(BigInteger)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
