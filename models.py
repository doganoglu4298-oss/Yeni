from dataclasses import dataclass,field,asdict
from enum import Enum
from datetime import datetime
from typing import Optional

class PositionSide(str,Enum):
 LONG="LONG"
 SHORT="SHORT"
class PositionStatus(str,Enum):
 OPEN="OPEN"
 CLOSED="CLOSED"
class MarketRegime(str,Enum):
 TREND="TREND"
 TRANSITION="TRANSITION"
 RANGE="RANGE"
class BotMode(str,Enum):
 AGGRESSIVE="AGGRESSIVE"
 NORMAL="NORMAL"
 DEFENSIVE="DEFENSIVE"
 PROTECTION="PROTECTION"
@dataclass
class Position:
 symbol:str
 side:PositionSide
 entry_price:float
 quantity:float
 stop_loss:float
 take_profit:float
 confidence:int
 market_score:int
 opened_at:datetime=field(default_factory=datetime.utcnow)
 status:PositionStatus=PositionStatus.OPEN
 exit_price:Optional[float]=None
 pnl:float=0.0
 def close(self,exit_price:float):
  self.exit_price=exit_price
  self.pnl=((exit_price-self.entry_price) if self.side==PositionSide.LONG else (self.entry_price-exit_price))*self.quantity
  self.status=PositionStatus.CLOSED
 def to_dict(self):
  d=asdict(self);d["opened_at"]=self.opened_at.isoformat();d["side"]=self.side.value;d["status"]=self.status.value;return d
