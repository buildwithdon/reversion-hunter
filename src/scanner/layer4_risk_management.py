"""
Layer 4: Risk Management and Position Sizing
Final validation layer before trade signals
"""
from typing import List, Optional, Union, Tuple
import logging

from ..models.stock import Stock
from ..models.option import PutSpread, CallSpread, SpreadType
from ..models.trade import Trade, Portfolio
from ..calculations.expected_value import ExpectedValueCalculator
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


class RiskManagementScanner:
    """
    Layer 4: Risk Management and Portfolio Constraints

    Criteria:
    - Position Size: Max 2-5% of portfolio per trade
    - Take Profit: 50% of max profit
    - Stop Loss: 2x premium collected OR 50% of spread width loss
    - Portfolio Correlation: Max 3 trades in same sector
    - Expected Value: Minimum 20% (configurable)
    """

    def __init__(
        self,
        portfolio_size: float = 100000,
        max_position_size_percent: float = 2.5,
        max_positions: int = 15,
        max_sector_positions: int = 3,
        min_expected_value: float = 0.20
    ):
        self.portfolio_size = portfolio_size
        self.max_position_size_percent = max_position_size_percent
        self.max_positions = max_positions
        self.max_sector_positions = max_sector_positions
        self.min_expected_value = min_expected_value
        self.ev_calc = ExpectedValueCalculator()

    def evaluate_spread(
        self,
        spread: Union[PutSpread, CallSpread],
        stock: Stock
    ) -> Tuple[bool, dict]:
        """
        Evaluate if spread passes risk management criteria

        Args:
            spread: PutSpread or CallSpread object
            stock: Stock object with fundamentals

        Returns:
            (passes, details_dict)
        """
        details = {
            'passes': False,
            'failures': [],
            'expected_value': None,
            'ev_percent': None,
            'position_size': None,
            'capital_at_risk': None,
            'take_profit': None,
            'stop_loss': None
        }

        # Calculate Expected Value
        if isinstance(spread, PutSpread):
            ev_metrics = self.ev_calc.calculate_credit_spread_ev(
                premium_collected=spread.net_premium_collected,
                max_loss=spread.max_loss,
                probability_of_profit=spread.probability_of_profit or 80
            )
        else:  # CallSpread
            ev_metrics = self.ev_calc.calculate_debit_spread_ev(
                max_profit=spread.max_profit,
                debit_paid=spread.net_debit_paid,
                probability_of_profit=spread.probability_of_profit or 65
            )

        details['expected_value'] = ev_metrics['expected_value']
        details['ev_percent'] = ev_metrics['ev_percent']

        # Check EV threshold
        if ev_metrics['ev_percent'] < self.min_expected_value * 100:
            details['failures'].append(
                f"EV {ev_metrics['ev_percent']:.1f}% < {self.min_expected_value*100}%"
            )

        # Calculate position size
        max_capital_per_trade = self.portfolio_size * (self.max_position_size_percent / 100)

        if isinstance(spread, PutSpread):
            capital_at_risk = spread.max_loss * 100  # Per contract
            position_size_capital = spread.net_premium_collected * 100
        else:
            capital_at_risk = spread.net_debit_paid * 100
            position_size_capital = spread.net_debit_paid * 100

        details['capital_at_risk'] = capital_at_risk
        details['position_size'] = position_size_capital

        # Check if position size is within limits
        if capital_at_risk > max_capital_per_trade:
            details['failures'].append(
                f"Capital at risk ${capital_at_risk:.0f} > max ${max_capital_per_trade:.0f}"
            )

        # Calculate take profit and stop loss
        if isinstance(spread, PutSpread):
            # Take profit at 50% of max profit
            take_profit_dollars = spread.max_profit * 0.5 * 100
            # Stop loss at 2x premium collected
            stop_loss_dollars = spread.net_premium_collected * 2 * 100
        else:
            # Take profit at 50% of max profit
            take_profit_dollars = spread.max_profit * 0.5 * 100
            # Stop loss at 50% of spread width
            stop_loss_dollars = spread.strike_width * 0.5 * 100

        details['take_profit'] = take_profit_dollars
        details['stop_loss'] = stop_loss_dollars

        # Check if no failures
        details['passes'] = len(details['failures']) == 0

        return details['passes'], details

    def create_trade_signal(
        self,
        spread: Union[PutSpread, CallSpread],
        stock: Stock,
        rsp_spy_spread: Optional[float] = None
    ) -> Optional[Trade]:
        """
        Create a Trade object if spread passes all risk management checks

        Args:
            spread: PutSpread or CallSpread
            stock: Stock object
            rsp_spy_spread: Current RSP vs SPY spread value

        Returns:
            Trade object or None if doesn't pass
        """
        # Evaluate spread
        passes, details = self.evaluate_spread(spread, stock)

        if not passes:
            logger.info(f"Spread for {stock.symbol} failed risk management: {details['failures']}")
            return None

        # Create Trade object
        trade_id = f"{stock.symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        if isinstance(spread, PutSpread):
            entry_price = spread.net_premium_collected
        else:
            entry_price = spread.net_debit_paid

        trade = Trade(
            trade_id=trade_id,
            symbol=stock.symbol,
            spread_type=spread.spread_type,
            spread=spread,
            quantity=1,  # Default 1 contract
            entry_price=entry_price,
            capital_at_risk=details['capital_at_risk'],
            position_size_percent=self.max_position_size_percent,
            expected_value=details['ev_percent'] / 100,
            probability_of_profit=spread.probability_of_profit or 80,
            rsp_spy_spread_at_entry=rsp_spy_spread,
            layer1_pass=stock.layer1_pass,
            layer2_pass=stock.layer2_pass,
            layer3_pass=True,  # Passed if we got here
            layer4_pass=True,  # Passed if we got here
            stop_loss=details['stop_loss'],
            take_profit=details['take_profit'],
            entry_notes=self._generate_entry_notes(stock, spread, details)
        )

        logger.info(f"Created trade signal for {stock.symbol}: EV={details['ev_percent']:.1f}%")
        return trade

    def scan_spreads(
        self,
        spreads_by_stock: dict[str, List[Union[PutSpread, CallSpread]]],
        stocks_by_symbol: dict[str, Stock],
        rsp_spy_spread: Optional[float] = None
    ) -> List[Trade]:
        """
        Scan all spreads and create trade signals for those passing Layer 4

        Args:
            spreads_by_stock: Dict mapping symbol to list of spreads
            stocks_by_symbol: Dict mapping symbol to Stock object
            rsp_spy_spread: Current RSP vs SPY spread

        Returns:
            List of Trade objects ready for execution
        """
        trade_signals = []

        for symbol, spreads in spreads_by_stock.items():
            stock = stocks_by_symbol.get(symbol)
            if not stock:
                continue

            for spread in spreads:
                trade = self.create_trade_signal(spread, stock, rsp_spy_spread)
                if trade:
                    trade_signals.append(trade)

        logger.info(f"Layer 4: Generated {len(trade_signals)} trade signals")
        return trade_signals

    def filter_by_sector_limits(
        self,
        trade_signals: List[Trade],
        stocks_by_symbol: dict[str, Stock],
        existing_positions: Optional[List[Trade]] = None
    ) -> List[Trade]:
        """
        Filter trades to respect sector concentration limits

        Args:
            trade_signals: List of potential trades
            stocks_by_symbol: Dict mapping symbols to stocks
            existing_positions: List of existing open positions

        Returns:
            Filtered list of trades
        """
        # Count existing positions by sector
        sector_counts = {}
        if existing_positions:
            for position in existing_positions:
                stock = stocks_by_symbol.get(position.symbol)
                if stock and stock.fundamentals and stock.fundamentals.sector:
                    sector = stock.fundamentals.sector
                    sector_counts[sector] = sector_counts.get(sector, 0) + 1

        # Filter new trades
        filtered_trades = []
        for trade in trade_signals:
            stock = stocks_by_symbol.get(trade.symbol)
            if not stock or not stock.fundamentals:
                continue

            sector = stock.fundamentals.sector
            if not sector:
                continue

            current_count = sector_counts.get(sector, 0)
            if current_count < self.max_sector_positions:
                filtered_trades.append(trade)
                sector_counts[sector] = current_count + 1
            else:
                logger.info(f"Skipping {trade.symbol}: sector {sector} limit reached")

        return filtered_trades

    def rank_trade_signals(self, trades: List[Trade]) -> List[Trade]:
        """
        Rank trade signals by overall quality

        Ranking criteria:
        1. Higher expected value
        2. Higher probability of profit
        3. Better risk/reward ratio
        """
        def trade_quality_score(trade: Trade) -> float:
            score = 0

            # EV score (0-100)
            if trade.expected_value:
                ev_score = min(trade.expected_value * 100, 100)
                score += ev_score * 0.5

            # Probability score (0-100)
            if trade.probability_of_profit:
                score += trade.probability_of_profit * 0.3

            # Risk/reward score
            if trade.take_profit and trade.stop_loss and trade.stop_loss > 0:
                rr_ratio = trade.take_profit / trade.stop_loss
                rr_score = min(rr_ratio / 2 * 100, 100)
                score += rr_score * 0.2

            return score

        return sorted(trades, key=trade_quality_score, reverse=True)

    def _generate_entry_notes(
        self,
        stock: Stock,
        spread: Union[PutSpread, CallSpread],
        risk_details: dict
    ) -> str:
        """Generate detailed entry notes for trade"""
        notes = []

        # Stock fundamentals
        if stock.fundamentals:
            notes.append(f"P/E: {stock.fundamentals.pe_ratio:.1f}")
            notes.append(f"ROE: {stock.fundamentals.roe:.1f}%")
            notes.append(f"Sector: {stock.fundamentals.sector}")

        # Technicals
        if stock.technicals:
            notes.append(f"RSI: {stock.technicals.rsi:.1f}")

        # Spread details
        if isinstance(spread, PutSpread):
            notes.append(f"Put Spread {spread.short_put.strike}/{spread.long_put.strike}")
            notes.append(f"Premium: ${spread.net_premium_collected:.2f}")
        else:
            notes.append(f"Call Spread {spread.long_call.strike}/{spread.short_call.strike}")
            notes.append(f"Debit: ${spread.net_debit_paid:.2f}")

        notes.append(f"DTE: {spread.dte}")
        notes.append(f"PoP: {spread.probability_of_profit:.1f}%")
        notes.append(f"EV: {risk_details['ev_percent']:.1f}%")

        return " | ".join(notes)

    def calculate_portfolio_metrics(self, trades: List[Trade]) -> dict:
        """
        Calculate portfolio-level metrics for a set of trades

        Args:
            trades: List of Trade objects

        Returns:
            Dict with portfolio metrics
        """
        total_capital_at_risk = sum(t.capital_at_risk for t in trades)
        total_expected_profit = sum(
            t.capital_at_risk * t.expected_value for t in trades
        )

        avg_prob_of_profit = sum(t.probability_of_profit for t in trades) / len(trades) if trades else 0
        avg_expected_value = sum(t.expected_value for t in trades) / len(trades) if trades else 0

        # Estimate portfolio returns (simple)
        # Assuming law of large numbers with 1000 trades
        if trades:
            simulation = self.ev_calc.simulate_1000_trades(
                win_rate=avg_prob_of_profit,
                avg_win=sum(t.take_profit for t in trades) / len(trades),
                avg_loss=sum(t.stop_loss for t in trades) / len(trades),
                starting_capital=self.portfolio_size
            )
        else:
            simulation = {}

        return {
            'num_positions': len(trades),
            'total_capital_at_risk': total_capital_at_risk,
            'capital_utilization_percent': (total_capital_at_risk / self.portfolio_size) * 100,
            'total_expected_profit': total_expected_profit,
            'average_probability_of_profit': avg_prob_of_profit,
            'average_expected_value': avg_expected_value,
            'simulated_1000_trades': simulation
        }
