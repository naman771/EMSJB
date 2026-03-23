from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.database import Base
from datetime import datetime


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    total_profit = Column(Float)
    steps_count = Column(Integer, default=0)

    steps = relationship("SimulationStep", back_populates="run", cascade="all, delete-orphan")


class SimulationStep(Base):
    __tablename__ = "simulation_steps"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_runs.id"))
    step_index = Column(Integer)
    price = Column(Float)
    forecast_price = Column(Float, default=0.0)
    battery_power = Column(Float)
    soc = Column(Float)
    profit = Column(Float)
    energy_revenue = Column(Float, default=0.0)
    degradation_cost = Column(Float, default=0.0)
    deviation_penalty = Column(Float, default=0.0)

    run = relationship("SimulationRun", back_populates="steps")
