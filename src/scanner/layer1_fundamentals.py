"""
Layer 1: Stock Fundamentals Scanner
Identify the diamonds - stocks with strong fundamentals
"""
from typing import List, Optional
import logging

from ..data.yahoo_finance import YahooFinanceClient
from ..models.stock import Stock, StockFundamentals

logger = logging.getLogger(__name__)


class FundamentalsScanner:
    """
    Layer 1: Screen stocks based on fundamental criteria

    Criteria:
    - P/E Ratio: 8-15x
    - Market Cap: >$10B
    - Negative Correlation to Mag 7: <-0.3
    - Sector: Financials, Healthcare, Consumer Staples, Utilities, Industrials
    - EPS Growth: Positive for last 2 quarters
    - Debt-to-Equity: <1.5
    - ROE: >12%
    """

    def __init__(self, data_client: Optional[YahooFinanceClient] = None):
        self.data_client = data_client or YahooFinanceClient()

        # Define allowed sectors
        self.allowed_sectors = [
            "Financials",
            "Healthcare",
            "Consumer Staples",
            "Utilities",
            "Industrials"
        ]

    def scan_symbol(self, symbol: str) -> Optional[Stock]:
        """
        Scan a single symbol for Layer 1 criteria

        Args:
            symbol: Stock ticker symbol

        Returns:
            Stock object with fundamentals and evaluation
        """
        try:
            # Fetch fundamentals
            fundamentals = self.data_client.get_stock_fundamentals(symbol)
            if not fundamentals:
                logger.warning(f"Could not fetch fundamentals for {symbol}")
                return None

            # Calculate Mag7 correlation
            mag7_corr = self.data_client.calculate_mag7_correlation(symbol)
            if mag7_corr is not None:
                fundamentals.correlation_to_mag7 = mag7_corr

            # Calculate SPY correlation
            spy_corr = self.data_client.calculate_correlation(symbol, "SPY")
            if spy_corr is not None:
                fundamentals.correlation_to_spy = spy_corr

            # Create Stock object
            stock = Stock(
                symbol=symbol,
                fundamentals=fundamentals
            )

            # Evaluate against Layer 1 criteria
            stock.evaluate()

            logger.info(f"Scanned {symbol}: Layer1 {'PASS' if stock.layer1_pass else 'FAIL'}")
            if not stock.layer1_pass:
                logger.debug(f"{symbol} failures: {stock.layer1_failures}")

            return stock

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            return None

    def scan_universe(self, symbols: List[str]) -> List[Stock]:
        """
        Scan a universe of stocks for Layer 1 criteria

        Args:
            symbols: List of ticker symbols

        Returns:
            List of Stock objects that pass Layer 1
        """
        passing_stocks = []

        for symbol in symbols:
            stock = self.scan_symbol(symbol)
            if stock and stock.layer1_pass:
                passing_stocks.append(stock)

        logger.info(f"Layer 1: {len(passing_stocks)}/{len(symbols)} stocks passed")
        return passing_stocks

    def get_default_universe(self) -> List[str]:
        """
        Get default universe of stocks to scan

        Returns large-cap stocks from allowed sectors
        """
        # Top stocks from each allowed sector
        # In production, this would come from a database or API
        universe = {
            "Financials": ["JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC", "TFC", "BK"],
            "Healthcare": ["JNJ", "UNH", "PFE", "ABT", "TMO", "MRK", "DHR", "BMY", "AMGN", "CVS"],
            "Consumer Staples": ["PG", "KO", "PEP", "WMT", "COST", "PM", "MO", "CL", "KMB", "GIS"],
            "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL", "WEC", "ES"],
            "Industrials": ["HON", "UPS", "BA", "CAT", "GE", "MMM", "LMT", "RTX", "DE", "UNP"]
        }

        # Flatten to single list
        all_symbols = []
        for sector_stocks in universe.values():
            all_symbols.extend(sector_stocks)

        return all_symbols

    def filter_by_pe_ratio(
        self,
        stocks: List[Stock],
        min_pe: float = 8.0,
        max_pe: float = 15.0
    ) -> List[Stock]:
        """Filter stocks by P/E ratio range"""
        return [
            s for s in stocks
            if s.fundamentals
            and s.fundamentals.pe_ratio is not None
            and min_pe <= s.fundamentals.pe_ratio <= max_pe
        ]

    def filter_by_market_cap(
        self,
        stocks: List[Stock],
        min_market_cap: float = 10_000_000_000
    ) -> List[Stock]:
        """Filter stocks by minimum market cap ($10B default)"""
        return [
            s for s in stocks
            if s.fundamentals
            and s.fundamentals.market_cap >= min_market_cap
        ]

    def filter_by_sector(self, stocks: List[Stock]) -> List[Stock]:
        """Filter stocks by allowed sectors"""
        return [
            s for s in stocks
            if s.fundamentals
            and s.fundamentals.sector in self.allowed_sectors
        ]

    def filter_by_mag7_correlation(
        self,
        stocks: List[Stock],
        max_correlation: float = -0.3
    ) -> List[Stock]:
        """Filter stocks by Mag7 correlation (must be negative)"""
        return [
            s for s in stocks
            if s.fundamentals
            and s.fundamentals.correlation_to_mag7 is not None
            and s.fundamentals.correlation_to_mag7 <= max_correlation
        ]

    def filter_by_roe(
        self,
        stocks: List[Stock],
        min_roe: float = 12.0
    ) -> List[Stock]:
        """Filter stocks by minimum ROE (12% default)"""
        return [
            s for s in stocks
            if s.fundamentals
            and s.fundamentals.roe is not None
            and s.fundamentals.roe >= min_roe
        ]

    def filter_by_debt_to_equity(
        self,
        stocks: List[Stock],
        max_de: float = 1.5
    ) -> List[Stock]:
        """Filter stocks by max debt-to-equity ratio"""
        return [
            s for s in stocks
            if s.fundamentals
            and s.fundamentals.debt_to_equity is not None
            and s.fundamentals.debt_to_equity <= max_de
        ]

    def rank_by_value(self, stocks: List[Stock]) -> List[Stock]:
        """
        Rank stocks by value metrics

        Ranking criteria:
        1. Lower P/E (more undervalued)
        2. Higher ROE (more profitable)
        3. Lower debt-to-equity (cleaner balance sheet)
        4. More negative Mag7 correlation (better diversification)
        """
        def value_score(stock: Stock) -> float:
            """Calculate composite value score"""
            if not stock.fundamentals:
                return 0

            score = 0

            # P/E score (lower is better, normalize to 0-100)
            if stock.fundamentals.pe_ratio:
                pe_score = max(0, (15 - stock.fundamentals.pe_ratio) / 7 * 100)
                score += pe_score * 0.3

            # ROE score (higher is better)
            if stock.fundamentals.roe:
                roe_score = min(100, (stock.fundamentals.roe / 20) * 100)
                score += roe_score * 0.3

            # D/E score (lower is better)
            if stock.fundamentals.debt_to_equity:
                de_score = max(0, (1.5 - stock.fundamentals.debt_to_equity) / 1.5 * 100)
                score += de_score * 0.2

            # Mag7 correlation score (more negative is better)
            if stock.fundamentals.correlation_to_mag7:
                corr_score = max(0, (-stock.fundamentals.correlation_to_mag7 - 0.3) / 0.7 * 100)
                score += corr_score * 0.2

            return score

        return sorted(stocks, key=value_score, reverse=True)
