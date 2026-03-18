from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    total_profit = Column(Float)
    
    steps = relationship("SimulationStep", back_populates="run")

class SimulationStep(Base):
    __tablename__ = "simulation_steps"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("simulation_runs.id"))
    step_index = Column(Integer)
    price = Column(Float)
    battery_power = Column(Float)
    soc = Column(Float)
    profit = Column(Float)

    run = relationship("SimulationRun", back_populates="steps")
