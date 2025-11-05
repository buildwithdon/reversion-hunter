"""
Expected Value calculations for option spreads
"""
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class ExpectedValueCalculator:
    """Calculate Expected Value (EV) for option spreads"""

    @staticmethod
    def calculate_credit_spread_ev(
        premium_collected: float,
        max_loss: float,
        probability_of_profit: float
    ) -> dict:
        """
        Calculate EV for credit spreads (put spreads, call credit spreads)

        Args:
            premium_collected: Net premium received
            max_loss: Maximum loss (strike width - premium)
            probability_of_profit: Probability of profit (0-100)

        Returns:
            Dict with EV, win_amount, loss_amount, profit_factor
        """
        win_prob = probability_of_profit / 100
        loss_prob = 1 - win_prob

        win_amount = premium_collected
        loss_amount = max_loss

        # EV = (Win% × Profit) - (Loss% × Loss)
        ev = (win_prob * win_amount) - (loss_prob * loss_amount)

        # Return on capital at risk
        if max_loss > 0:
            ev_percent = (ev / max_loss) * 100
            profit_factor = (win_prob * win_amount) / (loss_prob * loss_amount) if loss_prob > 0 else float('inf')
        else:
            ev_percent = 0
            profit_factor = 0

        return {
            'expected_value': ev,
            'ev_percent': ev_percent,
            'win_amount': win_amount,
            'loss_amount': loss_amount,
            'win_probability': win_prob,
            'loss_probability': loss_prob,
            'profit_factor': profit_factor
        }

    @staticmethod
    def calculate_debit_spread_ev(
        max_profit: float,
        debit_paid: float,
        probability_of_profit: float
    ) -> dict:
        """
        Calculate EV for debit spreads (call debit spreads)

        Args:
            max_profit: Maximum profit (strike width - debit paid)
            debit_paid: Net debit paid
            probability_of_profit: Probability of profit (0-100)

        Returns:
            Dict with EV, win_amount, loss_amount, profit_factor
        """
        win_prob = probability_of_profit / 100
        loss_prob = 1 - win_prob

        win_amount = max_profit
        loss_amount = debit_paid

        # EV = (Win% × Profit) - (Loss% × Loss)
        ev = (win_prob * win_amount) - (loss_prob * loss_amount)

        # Return on investment
        if debit_paid > 0:
            ev_percent = (ev / debit_paid) * 100
            profit_factor = (win_prob * win_amount) / (loss_prob * loss_amount) if loss_prob > 0 else float('inf')
        else:
            ev_percent = 0
            profit_factor = 0

        return {
            'expected_value': ev,
            'ev_percent': ev_percent,
            'win_amount': win_amount,
            'loss_amount': loss_amount,
            'win_probability': win_prob,
            'loss_probability': loss_prob,
            'profit_factor': profit_factor
        }

    @staticmethod
    def kelly_criterion(
        win_probability: float,
        win_amount: float,
        loss_amount: float
    ) -> float:
        """
        Calculate optimal position size using Kelly Criterion

        Args:
            win_probability: Probability of winning (0-1)
            win_amount: Amount won on winning trade
            loss_amount: Amount lost on losing trade

        Returns:
            Optimal fraction of capital to risk (0-1)
        """
        if loss_amount == 0:
            return 0

        b = win_amount / loss_amount  # Win/loss ratio
        p = win_probability
        q = 1 - p

        kelly = (b * p - q) / b

        # Use fractional Kelly (e.g., 25% of full Kelly) for safety
        fractional_kelly = max(0, min(kelly * 0.25, 0.05))  # Cap at 5%

        return fractional_kelly

    @staticmethod
    def sharpe_ratio(
        expected_return: float,
        standard_deviation: float,
        risk_free_rate: float = 0.05
    ) -> float:
        """
        Calculate Sharpe ratio for strategy

        Args:
            expected_return: Expected return (as decimal)
            standard_deviation: Standard deviation of returns
            risk_free_rate: Risk-free rate (as decimal, e.g., 0.05 for 5%)

        Returns:
            Sharpe ratio
        """
        if standard_deviation == 0:
            return 0

        return (expected_return - risk_free_rate) / standard_deviation

    @staticmethod
    def simulate_1000_trades(
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        starting_capital: float = 10000
    ) -> dict:
        """
        Monte Carlo simulation of 1000 trades

        Args:
            win_rate: Win rate (0-100)
            avg_win: Average win amount
            avg_loss: Average loss amount
            starting_capital: Starting capital

        Returns:
            Dict with simulation results
        """
        import random

        num_trades = 1000
        capital = starting_capital
        capital_history = [capital]

        wins = 0
        losses = 0
        total_profit = 0

        for _ in range(num_trades):
            if random.random() * 100 < win_rate:
                # Win
                profit = avg_win
                wins += 1
            else:
                # Loss
                profit = -avg_loss
                losses += 1

            capital += profit
            total_profit += profit
            capital_history.append(capital)

        final_return = ((capital - starting_capital) / starting_capital) * 100
        actual_win_rate = (wins / num_trades) * 100

        return {
            'starting_capital': starting_capital,
            'ending_capital': capital,
            'total_profit': total_profit,
            'total_return_percent': final_return,
            'wins': wins,
            'losses': losses,
            'actual_win_rate': actual_win_rate,
            'capital_history': capital_history,
            'max_drawdown': ExpectedValueCalculator._calculate_max_drawdown(capital_history),
        }

    @staticmethod
    def _calculate_max_drawdown(capital_history: list[float]) -> dict:
        """Calculate maximum drawdown from capital history"""
        peak = capital_history[0]
        max_dd = 0
        max_dd_percent = 0

        for capital in capital_history:
            if capital > peak:
                peak = capital

            dd = peak - capital
            dd_percent = (dd / peak) * 100 if peak > 0 else 0

            if dd > max_dd:
                max_dd = dd
                max_dd_percent = dd_percent

        return {
            'max_drawdown': max_dd,
            'max_drawdown_percent': max_dd_percent
        }

    @staticmethod
    def breakeven_win_rate(
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate breakeven win rate

        Args:
            avg_win: Average winning trade amount
            avg_loss: Average losing trade amount

        Returns:
            Breakeven win rate (0-100)
        """
        if avg_win + avg_loss == 0:
            return 50.0

        breakeven = (avg_loss / (avg_win + avg_loss)) * 100
        return breakeven

    @staticmethod
    def meets_ev_threshold(
        premium_collected: float,
        max_loss: float,
        probability_of_profit: float,
        threshold: float = 0.20
    ) -> Tuple[bool, dict]:
        """
        Check if credit spread meets EV threshold

        Args:
            premium_collected: Net premium received
            max_loss: Maximum loss
            probability_of_profit: Probability of profit (0-100)
            threshold: Minimum EV threshold (e.g., 0.20 = 20%)

        Returns:
            (passes, ev_metrics)
        """
        ev_metrics = ExpectedValueCalculator.calculate_credit_spread_ev(
            premium_collected, max_loss, probability_of_profit
        )

        passes = ev_metrics['ev_percent'] >= (threshold * 100)

        return passes, ev_metrics
