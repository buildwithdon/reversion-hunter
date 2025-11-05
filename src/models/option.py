"""
Options data model with Greeks
"""
from typing import Optional, Literal
from datetime import datetime, date
from pydantic import BaseModel, Field
from enum import Enum


class OptionType(str, Enum):
    CALL = "call"
    PUT = "put"


class SpreadType(str, Enum):
    PUT_SPREAD = "put_spread"  # Sell put spread (bullish/neutral)
    CALL_SPREAD = "call_spread"  # Buy call debit spread (bullish)
    IRON_CONDOR = "iron_condor"
    BUTTERFLY = "butterfly"


class OptionContract(BaseModel):
    """Individual option contract"""

    symbol: str = Field(..., description="Underlying stock symbol")
    strike: float = Field(..., gt=0)
    expiration: date
    option_type: OptionType

    # Pricing
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    mark: Optional[float] = None  # Mid price

    # Volume and Open Interest
    volume: Optional[int] = None
    open_interest: Optional[int] = None

    # Greeks
    delta: Optional[float] = Field(None, ge=-1, le=1)
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None

    # Volatility
    implied_volatility: Optional[float] = Field(None, ge=0, description="IV as decimal (e.g., 0.25 = 25%)")
    iv_percentile: Optional[float] = Field(None, ge=0, le=100, description="IV percentile rank")

    # Contract details
    contract_symbol: Optional[str] = None
    days_to_expiration: Optional[int] = None

    last_updated: datetime = Field(default_factory=datetime.utcnow)

    def __init__(self, **data):
        super().__init__(**data)
        if self.days_to_expiration is None and self.expiration:
            self.days_to_expiration = (self.expiration - date.today()).days


class PutSpread(BaseModel):
    """
    Bull Put Spread (Sell put spread)
    Sell higher strike put, buy lower strike put
    """

    symbol: str
    spread_type: SpreadType = SpreadType.PUT_SPREAD

    # Legs
    short_put: OptionContract  # Sell this
    long_put: OptionContract   # Buy this

    # Spread metrics
    strike_width: float = Field(..., gt=0)
    net_premium_collected: float = Field(..., description="Credit received")
    max_profit: float
    max_loss: float
    breakeven: float

    # Greeks for the spread
    delta: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    gamma: Optional[float] = None

    # Probability metrics
    probability_of_profit: Optional[float] = Field(None, ge=0, le=100)
    expected_value: Optional[float] = None

    # Evaluation
    dte: int = Field(..., description="Days to expiration")

    def __init__(self, **data):
        super().__init__(**data)
        # Calculate spread metrics
        self.strike_width = self.short_put.strike - self.long_put.strike
        self.max_profit = self.net_premium_collected
        self.max_loss = self.strike_width - self.net_premium_collected
        self.breakeven = self.short_put.strike - self.net_premium_collected

        # Aggregate Greeks
        if self.short_put.delta and self.long_put.delta:
            # Selling short put = positive delta, buying long put = negative delta
            self.delta = -self.short_put.delta + self.long_put.delta

        if self.short_put.theta and self.long_put.theta:
            # Selling = positive theta, buying = negative theta
            self.theta = -self.short_put.theta + self.long_put.theta

        if self.short_put.vega and self.long_put.vega:
            self.vega = -self.short_put.vega + self.long_put.vega

        if self.short_put.gamma and self.long_put.gamma:
            self.gamma = -self.short_put.gamma + self.long_put.gamma

        # Probability of profit from short put delta
        if self.short_put.delta:
            # For put, delta is negative; probability OTM = 1 - abs(delta)
            self.probability_of_profit = (1 - abs(self.short_put.delta)) * 100

    def premium_to_width_ratio(self) -> float:
        """Calculate premium collected as % of strike width"""
        return (self.net_premium_collected / self.strike_width) * 100

    def passes_layer3_criteria(self) -> tuple[bool, list[str]]:
        """
        Check if put spread passes Layer 3 Greeks criteria
        Returns: (passes, [reasons if failed])
        """
        failures = []

        # Delta: 0.15-0.20 on short put (15-20% probability ITM)
        if self.short_put.delta is None:
            failures.append("Missing delta on short put")
        elif not (-0.20 <= self.short_put.delta <= -0.15):
            failures.append(f"Short put delta {self.short_put.delta} not in range -0.20 to -0.15")

        # Theta: >0.05 per day (positive for the spread)
        if self.theta is None or self.theta <= 0.05:
            failures.append(f"Theta {self.theta} <= 0.05")

        # IV Percentile: >67%
        if self.short_put.iv_percentile is None or self.short_put.iv_percentile <= 67:
            failures.append(f"IV percentile {self.short_put.iv_percentile} <= 67%")

        # Gamma: Low (<0.05) to avoid rapid delta changes
        if self.gamma is not None and abs(self.gamma) >= 0.05:
            failures.append(f"Gamma {self.gamma} >= 0.05")

        # DTE: 30-45 days
        if not (30 <= self.dte <= 45):
            failures.append(f"DTE {self.dte} not in range 30-45")

        # Strike width: $5-10
        if not (5 <= self.strike_width <= 10):
            failures.append(f"Strike width ${self.strike_width} not in range $5-10")

        # Premium/Width ratio: >15%
        ratio = self.premium_to_width_ratio()
        if ratio < 15:
            failures.append(f"Premium/width ratio {ratio:.1f}% < 15%")

        return (len(failures) == 0, failures)


class CallSpread(BaseModel):
    """
    Bull Call Spread (Buy call debit spread)
    Buy lower strike call, sell higher strike call
    """

    symbol: str
    spread_type: SpreadType = SpreadType.CALL_SPREAD

    # Legs
    long_call: OptionContract   # Buy this
    short_call: OptionContract  # Sell this

    # Spread metrics
    strike_width: float = Field(..., gt=0)
    net_debit_paid: float = Field(..., description="Debit paid")
    max_profit: float
    max_loss: float
    breakeven: float

    # Greeks for the spread
    delta: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    gamma: Optional[float] = None

    # Probability metrics
    probability_of_profit: Optional[float] = None
    expected_value: Optional[float] = None

    # Evaluation
    dte: int = Field(..., description="Days to expiration")

    def __init__(self, **data):
        super().__init__(**data)
        # Calculate spread metrics
        self.strike_width = self.short_call.strike - self.long_call.strike
        self.max_profit = self.strike_width - self.net_debit_paid
        self.max_loss = self.net_debit_paid
        self.breakeven = self.long_call.strike + self.net_debit_paid

        # Aggregate Greeks
        if self.long_call.delta and self.short_call.delta:
            self.delta = self.long_call.delta - self.short_call.delta

        if self.long_call.theta and self.short_call.theta:
            self.theta = self.long_call.theta - self.short_call.theta

        if self.long_call.vega and self.short_call.vega:
            self.vega = self.long_call.vega - self.short_call.vega

        if self.long_call.gamma and self.short_call.gamma:
            self.gamma = self.long_call.gamma - self.short_call.gamma

        # Probability from long call delta
        if self.long_call.delta:
            self.probability_of_profit = self.long_call.delta * 100

    def risk_reward_ratio(self) -> float:
        """Calculate risk/reward ratio"""
        if self.max_loss > 0:
            return self.max_profit / self.max_loss
        return 0

    def passes_layer3_criteria(self) -> tuple[bool, list[str]]:
        """
        Check if call spread passes Layer 3 Greeks criteria
        Returns: (passes, [reasons if failed])
        """
        failures = []

        # Delta: 0.60-0.70 on long call
        if self.long_call.delta is None:
            failures.append("Missing delta on long call")
        elif not (0.60 <= self.long_call.delta <= 0.70):
            failures.append(f"Long call delta {self.long_call.delta} not in range 0.60-0.70")

        # Theta: Acceptable (<-0.03/day)
        if self.theta is not None and self.theta < -0.03:
            failures.append(f"Theta {self.theta} too negative")

        # IV Percentile: 30-50%
        if self.long_call.iv_percentile is None:
            failures.append("Missing IV percentile")
        elif not (30 <= self.long_call.iv_percentile <= 50):
            failures.append(f"IV percentile {self.long_call.iv_percentile} not in range 30-50%")

        # DTE: 60-90 days
        if not (60 <= self.dte <= 90):
            failures.append(f"DTE {self.dte} not in range 60-90")

        # Strike width: $5-10
        if not (5 <= self.strike_width <= 10):
            failures.append(f"Strike width ${self.strike_width} not in range $5-10")

        # Risk/Reward: >2:1
        rr = self.risk_reward_ratio()
        if rr < 2.0:
            failures.append(f"Risk/reward {rr:.2f} < 2.0")

        return (len(failures) == 0, failures)
