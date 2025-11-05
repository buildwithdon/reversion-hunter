"""
Layer 2: Mean Reversion Trigger Scanner
Identify entry signals for oversold stocks
"""
from typing import List, Optional
import logging

from ..data.yahoo_finance import YahooFinanceClient
from ..calculations.spreads import SpreadCalculator
from ..models.stock import Stock, StockTechnicals

logger = logging.getLogger(__name__)


class MeanReversionScanner:
    """
    Layer 2: Identify mean reversion triggers

    Criteria:
    - RSP vs SPY Spread: >8% divergence
    - Stock-Specific RSI: 30-45 (oversold but stable)
    - Volume: Above 20-day average
    - Price Action: Within 10% of 52-week low BUT above support
    """

    def __init__(self, data_client: Optional[YahooFinanceClient] = None):
        self.data_client = data_client or YahooFinanceClient()
        self.spread_calc = SpreadCalculator()

    def scan_symbol(self, stock: Stock) -> Stock:
        """
        Scan a stock for Layer 2 mean reversion triggers

        Args:
            stock: Stock object with fundamentals already evaluated

        Returns:
            Stock object with technicals and Layer 2 evaluation
        """
        try:
            # Fetch technical indicators
            technicals = self.data_client.get_stock_technicals(stock.symbol)
            if not technicals:
                logger.warning(f"Could not fetch technicals for {stock.symbol}")
                return stock

            stock.technicals = technicals

            # Evaluate against Layer 2 criteria
            stock.evaluate()

            logger.info(f"Scanned {stock.symbol}: Layer2 {'PASS' if stock.layer2_pass else 'FAIL'}")
            if not stock.layer2_pass:
                logger.debug(f"{stock.symbol} Layer2 failures: {stock.layer2_failures}")

            return stock

        except Exception as e:
            logger.error(f"Error scanning {stock.symbol} for Layer 2: {e}")
            return stock

    def scan_stocks(self, stocks: List[Stock]) -> List[Stock]:
        """
        Scan list of stocks for Layer 2 criteria

        Args:
            stocks: List of stocks that passed Layer 1

        Returns:
            List of stocks that pass both Layer 1 and Layer 2
        """
        passing_stocks = []

        for stock in stocks:
            stock = self.scan_symbol(stock)
            if stock.layer1_pass and stock.layer2_pass:
                passing_stocks.append(stock)

        logger.info(f"Layer 2: {len(passing_stocks)}/{len(stocks)} stocks passed")
        return passing_stocks

    def get_rsp_spy_spread(self) -> dict:
        """
        Calculate current RSP vs SPY spread

        Returns:
            Dict with spread metrics and statistics
        """
        try:
            # Get historical data for both
            rsp_hist = self.data_client.get_historical_prices("RSP", period="1y")
            spy_hist = self.data_client.get_historical_prices("SPY", period="1y")

            if rsp_hist.empty or spy_hist.empty:
                logger.error("Could not fetch RSP/SPY historical data")
                return {}

            # Calculate spread history
            spread_hist = self.spread_calc.calculate_historical_spread(rsp_hist, spy_hist)

            if spread_hist.empty:
                return {}

            # Get spread statistics
            stats = self.spread_calc.get_spread_statistics(spread_hist)

            # Check if at extreme
            is_extreme, extreme_details = self.spread_calc.is_spread_at_extreme(
                stats['current'],
                threshold=8.0,
                direction="positive"
            )

            # Calculate reversion probability
            reversion_prob = self.spread_calc.calculate_reversion_probability(
                spread_hist,
                stats['current']
            )

            # Get rotation signal
            rotation_signal = self.spread_calc.get_sector_rotation_signal(stats, threshold=8.0)

            return {
                'current_spread': stats['current'],
                'spread_stats': stats,
                'is_extreme': is_extreme,
                'extreme_details': extreme_details,
                'reversion_probability': reversion_prob,
                'rotation_signal': rotation_signal,
                'spread_history': spread_hist
            }

        except Exception as e:
            logger.error(f"Error calculating RSP/SPY spread: {e}")
            return {}

    def is_spread_trigger_active(self, threshold: float = 8.0) -> bool:
        """
        Check if RSP vs SPY spread trigger is active

        Args:
            threshold: Spread threshold (default 8%)

        Returns:
            True if spread is at or above threshold
        """
        spread_data = self.get_rsp_spy_spread()
        if not spread_data:
            return False

        return spread_data.get('is_extreme', False)

    def filter_by_rsi(
        self,
        stocks: List[Stock],
        min_rsi: float = 30,
        max_rsi: float = 45
    ) -> List[Stock]:
        """Filter stocks by RSI range (oversold but stable)"""
        return [
            s for s in stocks
            if s.technicals
            and s.technicals.rsi is not None
            and min_rsi <= s.technicals.rsi <= max_rsi
        ]

    def filter_by_volume(self, stocks: List[Stock]) -> List[Stock]:
        """Filter stocks with above-average volume"""
        return [
            s for s in stocks
            if s.technicals
            and s.technicals.volume_ratio is not None
            and s.technicals.volume_ratio > 1.0
        ]

    def filter_near_52w_low(
        self,
        stocks: List[Stock],
        max_distance: float = 10.0
    ) -> List[Stock]:
        """Filter stocks within X% of 52-week low"""
        return [
            s for s in stocks
            if s.technicals
            and s.technicals.distance_from_52w_low is not None
            and s.technicals.distance_from_52w_low <= max_distance
        ]

    def rank_by_mean_reversion_strength(self, stocks: List[Stock]) -> List[Stock]:
        """
        Rank stocks by mean reversion setup strength

        Ranking criteria:
        1. Lower RSI (more oversold)
        2. Higher volume ratio (more conviction)
        3. Closer to 52-week low
        4. Price above support levels
        """
        def reversion_score(stock: Stock) -> float:
            """Calculate composite mean reversion score"""
            if not stock.technicals:
                return 0

            score = 0

            # RSI score (lower within range is better)
            if stock.technicals.rsi:
                # Ideal RSI is 35 (middle of 30-45 range)
                rsi_deviation = abs(stock.technicals.rsi - 35)
                rsi_score = max(0, (15 - rsi_deviation) / 15 * 100)
                score += rsi_score * 0.35

            # Volume ratio score (higher is better)
            if stock.technicals.volume_ratio:
                vol_score = min(100, (stock.technicals.volume_ratio - 1) * 50)
                score += vol_score * 0.25

            # Distance from 52w low score (closer is better)
            if stock.technicals.distance_from_52w_low is not None:
                low_score = max(0, (10 - stock.technicals.distance_from_52w_low) / 10 * 100)
                score += low_score * 0.25

            # Trend score (near support)
            if stock.technicals.sma_20 and stock.technicals.current_price:
                # Price near but above 20-day SMA is good
                distance_from_sma = ((stock.technicals.current_price - stock.technicals.sma_20)
                                    / stock.technicals.sma_20 * 100)
                if -5 <= distance_from_sma <= 0:
                    trend_score = 100
                else:
                    trend_score = max(0, 100 - abs(distance_from_sma) * 10)
                score += trend_score * 0.15

            return score

        return sorted(stocks, key=reversion_score, reverse=True)

    def get_mean_reversion_strength_explanation(self, stock: Stock) -> str:
        """
        Generate explanation for why stock is a mean reversion candidate

        Args:
            stock: Stock object with technicals

        Returns:
            Human-readable explanation
        """
        if not stock.technicals:
            return "No technical data available"

        reasons = []

        # RSI
        if stock.technicals.rsi:
            if stock.technicals.rsi < 35:
                reasons.append(f"RSI at {stock.technicals.rsi:.1f} indicates oversold conditions")
            elif stock.technicals.rsi < 45:
                reasons.append(f"RSI at {stock.technicals.rsi:.1f} shows selling pressure easing")

        # Volume
        if stock.technicals.volume_ratio and stock.technicals.volume_ratio > 1.2:
            reasons.append(f"Volume {stock.technicals.volume_ratio:.1f}x above average - institutional interest")

        # Price level
        if stock.technicals.distance_from_52w_low is not None:
            reasons.append(f"Trading {stock.technicals.distance_from_52w_low:.1f}% above 52-week low")

        # Trend
        if stock.technicals.sma_20 and stock.technicals.current_price:
            if stock.technicals.current_price < stock.technicals.sma_20:
                reasons.append("Price below 20-day average - potential reversal setup")

        return " | ".join(reasons) if reasons else "Mean reversion criteria met"
