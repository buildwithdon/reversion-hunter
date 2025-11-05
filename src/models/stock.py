"""
Stock data model with fundamental metrics
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class StockFundamentals(BaseModel):
    """Stock fundamental metrics for Layer 1 screening"""

    symbol: str = Field(..., description="Stock ticker symbol")
    company_name: Optional[str] = None

    # Price metrics
    current_price: float = Field(..., gt=0)
    market_cap: float = Field(..., gt=0)

    # Valuation metrics
    pe_ratio: Optional[float] = Field(None, description="Price-to-Earnings ratio")
    forward_pe: Optional[float] = None
    peg_ratio: Optional[float] = None

    # Profitability metrics
    roe: Optional[float] = Field(None, description="Return on Equity (%)")
    profit_margin: Optional[float] = None
    operating_margin: Optional[float] = None

    # Balance sheet metrics
    debt_to_equity: Optional[float] = Field(None, description="Debt-to-Equity ratio")
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None

    # Growth metrics
    eps_current: Optional[float] = None
    eps_q1_ago: Optional[float] = None
    eps_q2_ago: Optional[float] = None
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None

    # Sector and industry
    sector: Optional[str] = None
    industry: Optional[str] = None

    # Correlation metrics
    correlation_to_spy: Optional[float] = None
    correlation_to_mag7: Optional[float] = None
    beta: Optional[float] = None

    # Volume and liquidity
    avg_volume: Optional[float] = None
    volume: Optional[float] = None

    # Price levels
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None

    # Timestamp
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "JPM",
                "company_name": "JPMorgan Chase & Co.",
                "current_price": 145.50,
                "market_cap": 420000000000,
                "pe_ratio": 10.5,
                "roe": 15.2,
                "debt_to_equity": 1.2,
                "sector": "Financials",
                "correlation_to_mag7": -0.35
            }
        }

    def eps_growth_positive_2q(self) -> bool:
        """Check if EPS growth is positive for last 2 quarters"""
        if self.eps_current and self.eps_q1_ago and self.eps_q2_ago:
            return (self.eps_current > self.eps_q1_ago > self.eps_q2_ago)
        return False

    def passes_layer1_criteria(self) -> tuple[bool, list[str]]:
        """
        Check if stock passes Layer 1 fundamental screening
        Returns: (passes, [reasons if failed])
        """
        failures = []

        # P/E Ratio: 8-15x
        if self.pe_ratio is None or not (8 <= self.pe_ratio <= 15):
            failures.append(f"P/E {self.pe_ratio} not in range 8-15")

        # Market Cap: >$10B
        if self.market_cap < 10_000_000_000:
            failures.append(f"Market cap ${self.market_cap/1e9:.1f}B < $10B")

        # Negative correlation to Mag 7: <-0.3
        if self.correlation_to_mag7 is None or self.correlation_to_mag7 >= -0.3:
            failures.append(f"Mag7 correlation {self.correlation_to_mag7} not < -0.3")

        # Sector filter
        allowed_sectors = ["Financials", "Healthcare", "Consumer Staples",
                          "Utilities", "Industrials"]
        if self.sector not in allowed_sectors:
            failures.append(f"Sector '{self.sector}' not in allowed list")

        # EPS Growth: Positive for last 2 quarters
        if not self.eps_growth_positive_2q():
            failures.append("EPS growth not positive for last 2 quarters")

        # Debt-to-Equity: <1.5
        if self.debt_to_equity is None or self.debt_to_equity >= 1.5:
            failures.append(f"Debt-to-Equity {self.debt_to_equity} >= 1.5")

        # ROE: >12%
        if self.roe is None or self.roe <= 12:
            failures.append(f"ROE {self.roe}% <= 12%")

        return (len(failures) == 0, failures)


class StockTechnicals(BaseModel):
    """Technical indicators for Layer 2 screening"""

    symbol: str

    # Price action
    current_price: float
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None

    # Momentum indicators
    rsi: Optional[float] = Field(None, description="Relative Strength Index")
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None

    # Volatility
    atr: Optional[float] = Field(None, description="Average True Range")
    bollinger_upper: Optional[float] = None
    bollinger_lower: Optional[float] = None

    # Volume
    volume: float
    avg_volume_20d: Optional[float] = None
    volume_ratio: Optional[float] = None  # current / avg

    # Support/Resistance levels
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    distance_from_52w_low: Optional[float] = None  # percentage

    last_updated: datetime = Field(default_factory=datetime.utcnow)

    def passes_layer2_criteria(self) -> tuple[bool, list[str]]:
        """
        Check if stock passes Layer 2 mean reversion trigger
        Returns: (passes, [reasons if failed])
        """
        failures = []

        # RSI: 30-45 (oversold but stable)
        if self.rsi is None or not (30 <= self.rsi <= 45):
            failures.append(f"RSI {self.rsi} not in range 30-45")

        # Volume: Above 20-day average
        if self.volume_ratio is None or self.volume_ratio <= 1.0:
            failures.append(f"Volume ratio {self.volume_ratio} <= 1.0")

        # Price within 10% of 52-week low
        if self.distance_from_52w_low is None or self.distance_from_52w_low > 10:
            failures.append(f"Distance from 52w low {self.distance_from_52w_low}% > 10%")

        return (len(failures) == 0, failures)


class Stock(BaseModel):
    """Complete stock data combining fundamentals and technicals"""

    symbol: str
    fundamentals: Optional[StockFundamentals] = None
    technicals: Optional[StockTechnicals] = None

    # Screening results
    layer1_pass: bool = False
    layer1_failures: list[str] = []
    layer2_pass: bool = False
    layer2_failures: list[str] = []

    last_updated: datetime = Field(default_factory=datetime.utcnow)

    def evaluate(self):
        """Evaluate stock against Layer 1 and 2 criteria"""
        if self.fundamentals:
            self.layer1_pass, self.layer1_failures = self.fundamentals.passes_layer1_criteria()

        if self.technicals:
            self.layer2_pass, self.layer2_failures = self.technicals.passes_layer2_criteria()
