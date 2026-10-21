import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def new_id() -> str:
    return uuid.uuid4().hex


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "document"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255))
    tags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    versions: Mapped[list["Version"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Version.seq"
    )


class Version(Base):
    __tablename__ = "version"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    parent_version_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size: Mapped[int] = mapped_column(Integer)
    pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    encrypted: Mapped[bool] = mapped_column(default=False)
    tool: Mapped[str | None] = mapped_column(String(64), nullable=True)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    document: Mapped[Document] = relationship(back_populates="versions")


class Task(Base):
    __tablename__ = "task"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tool: Mapped[str] = mapped_column(String(64))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(32), default="waiting")
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    files: Mapped[list["TaskFile"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="TaskFile.position"
    )


class TaskFile(Base):
    __tablename__ = "task_file"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("task.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(8))  # in | out
    position: Mapped[int] = mapped_column(Integer, default=0)
    version_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state: Mapped[str] = mapped_column(String(32), default="ok")
    task: Mapped[Task] = relationship(back_populates="files")


def make_session_factory(db_path: Path) -> sessionmaker:
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
