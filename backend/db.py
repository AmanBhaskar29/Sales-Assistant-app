# db.py
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Search(Base):
    __tablename__ = "searches"
    id = Column(Integer, primary_key=True)
    user_id = Column(String(64), nullable=True)  # Supabase user UUID when logged in
    query_text = Column(String(255), nullable=False)
    selected_name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    summary = relationship("Summary", back_populates="search", uselist=False, cascade="all,delete")
    news = relationship("NewsItem", back_populates="search", cascade="all,delete")

class Summary(Base):
    __tablename__ = "summaries"
    id = Column(Integer, primary_key=True)
    search_id = Column(Integer, ForeignKey("searches.id"), nullable=False)
    company_name = Column(String(255), nullable=False)
    official_website = Column(String(512))
    summary_text = Column(Text, nullable=False)
    llm_model = Column(String(64), default="gemini-2.5-flash")
    created_at = Column(DateTime, default=datetime.utcnow)
    search = relationship("Search", back_populates="summary")

class NewsItem(Base):
    __tablename__ = "news_items"
    id = Column(Integer, primary_key=True)
    search_id = Column(Integer, ForeignKey("searches.id"), nullable=False)
    title = Column(Text)
    description = Column(Text)
    url = Column(String(1024))
    source = Column(String(255))
    published_at = Column(String(64))
    rank = Column(Integer)  # 1..4
    created_at = Column(DateTime, default=datetime.utcnow)
    search = relationship("Search", back_populates="news")

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True)
    user_id = Column(String(64), nullable=False)
    title = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    messages = relationship("Message", back_populates="conversation", cascade="all,delete")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(16), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")

def init_db():
    Base.metadata.create_all(bind=engine)
