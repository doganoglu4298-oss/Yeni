"""
Trading Bot V6 Professional
models.py
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Optional

class PositionSide(str, Enum):
    LONG="LONG"
    SHORT="SHORT"

class PositionStatus(str, Enum):
    OPEN="OPEN"
    CLOSED="CLOSED"

class MarketRegime(str, Enum):
    TREND="TREND"
    TRANSITION="TRANSITION"
    RANGE="RANGE"

class BotMode(str, Enum):
    AGGRESSIVE="AGGRESSIVE"
    NORMAL="NORMAL"
    DEFENSIVE="DEFENSIVE"
    PROTECTION="PROTECTION"

class TradeResult(str, Enum):
    WIN="WIN"
    LOSS="LOSS"
    BREAKEVEN="BREAKEVEN"

@dataclass(slots=True)
class BaseModel:
    def to_dict(self)->dict[str,Any]:
        data=asdict(self)
        for k,v in list(data.items()):
            if isinstance(v,Enum):
                data[k]=v.value
            elif isinstance(v,datetime):
                data[k]=v.isoformat()
        return data

@dataclass(slots=True)
class Position(BaseModel):
    symbol:str
    side:PositionSide
    entry_price:float
    quantity:float
    stop_loss:float
    take_profit:float
    confidence:int
    market_score:int
    regime:MarketRegime
    entry_atr: float = 0.0
    opened_at:datetime=field(default_factory=datetime.utcnow)
    status:PositionStatus=PositionStatus.OPEN
    exit_price:Optional[float]=None
    closed_at:Optional[datetime]=None
    pnl:float=0.0
    pnl_percent:float=0.0
    highest_price:float=0.0
    lowest_price:float=0.0
    exit_reason:str=""
    signal_quality:int=0
    notification_sent:bool=False

    def __post_init__(self):
        self.highest_price=self.entry_price
        self.lowest_price=self.entry_price

    @property
    def is_open(self)->bool:
        return self.status==PositionStatus.OPEN

    @property
    def exit_time(self)->Optional[datetime]:
        # Backwards-compatible alias for closed_at.
        return self.closed_at

    # Backwards-compatible alias: some older code referred to this as
    # "close_reason". Kept as a property so both names always agree.
    @property
    def close_reason(self)->str:
        return self.exit_reason

    def close(self,exit_price:float,reason:str)->None:
        self.exit_price=exit_price
        self.closed_at=datetime.utcnow()
        self.status=PositionStatus.CLOSED
        self.exit_reason=reason
        if self.side==PositionSide.LONG:
            self.pnl=(exit_price-self.entry_price)*self.quantity
            self.pnl_percent=((exit_price-self.entry_price)/self.entry_price)*100
        else:
            self.pnl=(self.entry_price-exit_price)*self.quantity
            self.pnl_percent=((self.entry_price-exit_price)/self.entry_price)*100

    @property
    def result(self)->TradeResult:
        if self.pnl>0:return TradeResult.WIN
        if self.pnl<0:return TradeResult.LOSS
        return TradeResult.BREAKEVEN

@dataclass(slots=True)
class JournalEntry(BaseModel):
    symbol:str
    side:PositionSide
    entry_price:float
    exit_price:float
    quantity:float
    pnl:float
    pnl_percent:float
    confidence:int
    market_score:int
    regime:MarketRegime
    result:TradeResult
    exit_reason:str
    opened_at:datetime
    closed_at:datetime
    balance_after_trade:float

@dataclass(slots=True)
class LearningEntry(BaseModel):
    symbol:str
    confidence:int
    market_score:int
    regime:MarketRegime
    trend_strength:float
    volume_ratio:float
    atr:float
    rsi:float
    result:TradeResult
    pnl_percent:float
    created_at:datetime=field(default_factory=datetime.utcnow)
    notes:str=""

@dataclass(slots=True)
class BotStatistics(BaseModel):
    total_trades:int=0
    wins:int=0
    losses:int=0
    breakeven:int=0

__all__=["PositionSide","PositionStatus","MarketRegime","BotMode","TradeResult","Position","JournalEntry","LearningEntry","BotStatistics"]
