from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean, Text, DateTime,
    ForeignKey, UniqueConstraint, JSON
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .db import Base

class Author(Base):
    __tablename__ = "authors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

class Model(Base):
    __tablename__ = "models"
    # Full HF id (e.g. "google/gemma-2b") as PK
    id: Mapped[str] = mapped_column(String(512), primary_key=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("authors.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)  # split after '/'
    private: Mapped[bool] = mapped_column(Boolean, default=False)
    gated: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sha: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pipeline_tag: Mapped[str | None] = mapped_column(String(128), nullable=True)
    library_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    license: Mapped[str | None] = mapped_column(String(128), nullable=True)
    license_raw: Mapped[str | None] = mapped_column(String(128), nullable=True)
    downloads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_modified: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_storage: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    card_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    card_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    card_model_size: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    card_datasets: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    card_languages: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    transformers_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    gguf: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    safetensors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    author = relationship("Author", backref="models", lazy="joined")
    tags = relationship("ModelTag", back_populates="model", cascade="all, delete-orphan", lazy="selectin")
    siblings = relationship("Sibling", back_populates="model", cascade="all, delete-orphan", lazy="selectin")
    spaces = relationship("ModelSpace", back_populates="model", cascade="all, delete-orphan", lazy="selectin")

class Tag(Base):
    __tablename__ = "tags"
    name: Mapped[str] = mapped_column(String(255), primary_key=True)

class ModelTag(Base):
    __tablename__ = "model_tags"
    model_id: Mapped[str] = mapped_column(ForeignKey("models.id", ondelete="CASCADE"), primary_key=True)
    tag: Mapped[str] = mapped_column(ForeignKey("tags.name", ondelete="CASCADE"), primary_key=True)
    model = relationship("Model", back_populates="tags")
    tag_rel = relationship("Tag")

class Sibling(Base):
    __tablename__ = "siblings"
    model_id: Mapped[str] = mapped_column(ForeignKey("models.id", ondelete="CASCADE"), primary_key=True)
    rfilename: Mapped[str] = mapped_column(String(512), primary_key=True)
    model = relationship("Model", back_populates="siblings")

class Space(Base):
    __tablename__ = "spaces"
    name: Mapped[str] = mapped_column(String(512), primary_key=True)

class ModelSpace(Base):
    __tablename__ = "model_spaces"
    model_id: Mapped[str] = mapped_column(ForeignKey("models.id", ondelete="CASCADE"), primary_key=True)
    space_name: Mapped[str] = mapped_column(ForeignKey("spaces.name", ondelete="CASCADE"), primary_key=True)
    model = relationship("Model", back_populates="spaces")
    space = relationship("Space")
