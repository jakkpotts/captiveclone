"""
SQLAlchemy database models for CaptiveClone.
"""

import datetime
from typing import List

from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, DateTime, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from passlib.hash import argon2
from flask_login import UserMixin

Base = declarative_base()


class Network(Base):
    """Database model for a wireless network."""
    
    __tablename__ = "networks"
    
    id = Column(Integer, primary_key=True)
    ssid = Column(String(64))
    bssid = Column(String(17), unique=True)
    channel = Column(Integer, nullable=True)
    encryption = Column(Boolean, default=False)
    signal_strength = Column(Float, nullable=True)
    has_captive_portal = Column(Boolean, default=False)
    first_seen = Column(DateTime, default=datetime.datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    captive_portal = relationship("CaptivePortal", back_populates="network", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Network(ssid='{self.ssid}', bssid='{self.bssid}', has_captive_portal={self.has_captive_portal})>"


class CaptivePortal(Base):
    """Database model for a captive portal."""
    
    __tablename__ = "captive_portals"
    
    id = Column(Integer, primary_key=True)
    network_id = Column(Integer, ForeignKey("networks.id"))
    login_url = Column(String(512), nullable=True)
    redirect_url = Column(String(512), nullable=True)
    requires_authentication = Column(Boolean, default=False)
    form_data = Column(Text, nullable=True)  # Store form field data as JSON
    first_seen = Column(DateTime, default=datetime.datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    network = relationship("Network", back_populates="captive_portal")
    assets = relationship("PortalAsset", back_populates="portal", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<CaptivePortal(network='{self.network.ssid if self.network else None}', login_url='{self.login_url}')>"


class PortalAsset(Base):
    """Database model for a captive portal asset (CSS, JS, images, etc.)."""
    
    __tablename__ = "portal_assets"
    
    id = Column(Integer, primary_key=True)
    portal_id = Column(Integer, ForeignKey("captive_portals.id"))
    asset_type = Column(String(32))  # 'html', 'css', 'js', 'image', etc.
    url = Column(String(512))
    local_path = Column(String(512), nullable=True)
    content_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    portal = relationship("CaptivePortal", back_populates="assets")
    
    def __repr__(self) -> str:
        return f"<PortalAsset(type='{self.asset_type}', url='{self.url}')>"


class ScanSession(Base):
    """Database model for a scan session."""
    
    __tablename__ = "scan_sessions"
    
    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    interface = Column(String(32))
    networks_found = Column(Integer, default=0)
    captive_portals_found = Column(Integer, default=0)
    
    def __repr__(self) -> str:
        return f"<ScanSession(id={self.id}, start_time='{self.start_time}', networks_found={self.networks_found})>"


class User(Base, UserMixin):
    """Database model for application users (for authentication)."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), default="viewer")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # ----- password helpers -------------------------------------------------
    def set_password(self, password: str) -> None:
        """Hash *password* and store the hash in *password_hash*."""
        self.password_hash = argon2.hash(password)

    def check_password(self, password: str) -> bool:
        """Verify *password* against the stored *password_hash*."""
        try:
            return argon2.verify(password, self.password_hash)
        except ValueError:
            # If the hash is invalid/corrupted treat as failed auth
            return False

    # Flask-Login integration helpers ---------------------------------------
    def get_id(self):  # type: ignore[override]
        return str(self.id)


def init_db(db_path: str) -> None:
    """
    Initialize the database.
    
    Args:
        db_path: Path to the SQLite database file
    """
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return engine


def get_session(engine):
    """
    Get a database session.
    
    Args:
        engine: SQLAlchemy engine
        
    Returns:
        SQLAlchemy session
    """
    Session = sessionmaker(bind=engine)
    return Session() 