import os
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://bpo_user:bpo_pass@localhost:5432/bpodb"
)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class FlowRun(Base):
    __tablename__ = "flow_runs"

    run_id = Column(String, primary_key=True, index=True)
    flow_type = Column(String, index=True, nullable=False)
    queue_id = Column(String, index=True, nullable=False)
    time_window = Column(String, nullable=False)
    status = Column(String, nullable=False)  # approved, rejected, edited
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Store the entire BPOFlowState dump as a JSONB payload
    results_data = Column(JSONB, nullable=False)
