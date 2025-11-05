"""
Trade model for position tracking and management
"""
from typing import Optional, Union
from datetime import datetime, date
from enum import Enum
from pydantic import BaseModel, Field

from .option import PutSpread, CallSpread, SpreadType


class TradeStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    EXPIRED = "expired"


class TradeOutcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    PENDING = "pending"


class Trade(BaseModel):
    """Position tracking for option spreads"""

    # Identification
    trade_id: str = Field(..., description="Unique trade identifier")
    symbol: str
    spread_type: SpreadType

    # Trade details
    spread: Union[PutSpread, CallSpread]
    quantity: int = Field(default=1, gt=0, description="Number of contracts")

    # Entry
    entry_date: datetime = Field(default_factory=datetime.utcnow)
    entry_price: float = Field(..., description="Net credit/debit at entry")

    # Exit (if closed)
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None

    # P&L
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    realized_pnl: Optional[float] = None
    pnl_percent: Optional[float] = None

    # Risk management
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    profit_target_hit: bool = False
    stop_loss_hit: bool = False

    # Position sizing
    capital_at_risk: float = Field(..., description="Max loss amount")
    position_size_percent: float = Field(..., description="% of portfolio")

    # Status
    status: TradeStatus = TradeStatus.PENDING
    outcome: TradeOutcome = TradeOutcome.PENDING

    # Screening metadata
    expected_value: float
    probability_of_profit: float
    rsp_spy_spread_at_entry: Optional[float] = None

    # Layer results
    layer1_pass: bool = False
    layer2_pass: bool = False
    layer3_pass: bool = False
    layer4_pass: bool = False

    # Notes
    entry_notes: Optional[str] = None
    exit_notes: Optional[str] = None

    last_updated: datetime = Field(default_factory=datetime.utcnow)

    def update_pnl(self, current_spread_price: float):
        """Update unrealized P&L based on current spread price"""
        self.current_price = current_spread_price

        if self.spread_type == SpreadType.PUT_SPREAD:
            # For credit spread: profit when price decreases
            # Entry price is credit received (positive)
            # Current price is what we'd pay to close
            self.unrealized_pnl = (self.entry_price - current_spread_price) * self.quantity * 100
        else:  # CALL_SPREAD
            # For debit spread: profit when price increases
            # Entry price is debit paid (positive)
            # Current price is what we'd receive to close
            self.unrealized_pnl = (current_spread_price - self.entry_price) * self.quantity * 100

        if self.capital_at_risk > 0:
            self.pnl_percent = (self.unrealized_pnl / self.capital_at_risk) * 100

        self.last_updated = datetime.utcnow()

        # Check if targets hit
        if self.take_profit and self.unrealized_pnl >= self.take_profit:
            self.profit_target_hit = True

        if self.stop_loss and self.unrealized_pnl <= -self.stop_loss:
            self.stop_loss_hit = True

    def close_trade(self, exit_price: float, notes: Optional[str] = None):
        """Close the trade and calculate realized P&L"""
        self.exit_date = datetime.utcnow()
        self.exit_price = exit_price
        self.exit_notes = notes
        self.status = TradeStatus.CLOSED

        if self.spread_type == SpreadType.PUT_SPREAD:
            self.realized_pnl = (self.entry_price - exit_price) * self.quantity * 100
        else:  # CALL_SPREAD
            self.realized_pnl = (exit_price - self.entry_price) * self.quantity * 100

        if self.capital_at_risk > 0:
            self.pnl_percent = (self.realized_pnl / self.capital_at_risk) * 100

        # Determine outcome
        if self.realized_pnl > 0:
            self.outcome = TradeOutcome.WIN
        elif self.realized_pnl < 0:
            self.outcome = TradeOutcome.LOSS
        else:
            self.outcome = TradeOutcome.BREAKEVEN

        self.last_updated = datetime.utcnow()

    def should_close_for_profit(self, profit_percent: float = 50) -> bool:
        """Check if trade should be closed based on profit target"""
        if self.pnl_percent is None:
            return False

        max_profit = self.spread.max_profit if hasattr(self.spread, 'max_profit') else 0
        if max_profit == 0:
            return False

        target_profit = max_profit * (profit_percent / 100)
        return self.unrealized_pnl >= target_profit

    def should_close_for_loss(self) -> bool:
        """Check if stop loss should be triggered"""
        return self.stop_loss_hit

    def days_in_trade(self) -> int:
        """Calculate days since entry"""
        end_date = self.exit_date if self.exit_date else datetime.utcnow()
        return (end_date - self.entry_date).days

    def to_dict(self) -> dict:
        """Convert to dictionary for display"""
        return {
            "Trade ID": self.trade_id,
            "Symbol": self.symbol,
            "Type": self.spread_type.value,
            "Status": self.status.value,
            "Entry Date": self.entry_date.strftime("%Y-%m-%d"),
            "Entry Price": f"${self.entry_price:.2f}",
            "Current Price": f"${self.current_price:.2f}" if self.current_price else "N/A",
            "Unrealized P&L": f"${self.unrealized_pnl:.2f}" if self.unrealized_pnl else "N/A",
            "P&L %": f"{self.pnl_percent:.1f}%" if self.pnl_percent else "N/A",
            "Outcome": self.outcome.value,
            "Probability": f"{self.probability_of_profit:.1f}%",
            "Expected Value": f"{self.expected_value:.2%}",
        }


class Portfolio(BaseModel):
    """Portfolio tracking and management"""

    # Portfolio configuration
    total_capital: float = Field(..., gt=0)
    max_position_size_percent: float = Field(default=2.5, gt=0, le=100)
    max_positions: int = Field(default=15, gt=0)
    max_sector_positions: int = Field(default=3, gt=0)

    # Positions
    open_trades: list[Trade] = []
    closed_trades: list[Trade] = []

    # Performance metrics
    total_realized_pnl: float = 0.0
    total_unrealized_pnl: float = 0.0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    total_return_percent: float = 0.0

    # Risk metrics
    capital_deployed: float = 0.0
    capital_at_risk: float = 0.0

    last_updated: datetime = Field(default_factory=datetime.utcnow)

    def add_trade(self, trade: Trade) -> bool:
        """Add a new trade if within limits"""
        # Check max positions
        if len(self.open_trades) >= self.max_positions:
            return False

        # Check position size
        max_risk = self.total_capital * (self.max_position_size_percent / 100)
        if trade.capital_at_risk > max_risk:
            return False

        self.open_trades.append(trade)
        self.capital_at_risk += trade.capital_at_risk
        self.last_updated = datetime.utcnow()
        return True

    def close_trade(self, trade_id: str, exit_price: float, notes: Optional[str] = None):
        """Close a trade by ID"""
        for i, trade in enumerate(self.open_trades):
            if trade.trade_id == trade_id:
                trade.close_trade(exit_price, notes)
                self.closed_trades.append(trade)
                self.open_trades.pop(i)
                self.capital_at_risk -= trade.capital_at_risk

                # Update performance metrics
                if trade.realized_pnl:
                    self.total_realized_pnl += trade.realized_pnl
                    if trade.outcome == TradeOutcome.WIN:
                        self.win_count += 1
                    elif trade.outcome == TradeOutcome.LOSS:
                        self.loss_count += 1

                self.calculate_metrics()
                return True
        return False

    def update_all_positions(self, current_prices: dict[str, float]):
        """Update P&L for all open positions"""
        self.total_unrealized_pnl = 0
        for trade in self.open_trades:
            if trade.trade_id in current_prices:
                trade.update_pnl(current_prices[trade.trade_id])
                if trade.unrealized_pnl:
                    self.total_unrealized_pnl += trade.unrealized_pnl

        self.calculate_metrics()

    def calculate_metrics(self):
        """Calculate portfolio performance metrics"""
        total_trades = self.win_count + self.loss_count
        if total_trades > 0:
            self.win_rate = (self.win_count / total_trades) * 100

        if self.total_capital > 0:
            total_pnl = self.total_realized_pnl + self.total_unrealized_pnl
            self.total_return_percent = (total_pnl / self.total_capital) * 100

        self.last_updated = datetime.utcnow()

    def get_sector_exposure(self) -> dict[str, int]:
        """Get count of positions per sector"""
        sector_counts = {}
        for trade in self.open_trades:
            # Would need to lookup sector from symbol
            # Placeholder for now
            pass
        return sector_counts

    def available_capital(self) -> float:
        """Calculate available capital for new trades"""
        return self.total_capital - self.capital_at_risk
