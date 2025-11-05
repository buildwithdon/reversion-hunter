"""
RSP vs SPY spread calculations and market metrics
"""
import pandas as pd
import numpy as np
from typing import Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class SpreadCalculator:
    """Calculate RSP vs SPY spread and related metrics"""

    @staticmethod
    def calculate_rsp_spy_spread(
        rsp_price: float,
        spy_price: float,
        normalize: bool = True
    ) -> float:
        """
        Calculate current RSP vs SPY spread

        Args:
            rsp_price: Current RSP price
            spy_price: Current SPY price
            normalize: Whether to normalize prices (recommended)

        Returns:
            Spread as percentage
        """
        if normalize:
            # Normalize to 100 for comparison
            rsp_norm = 100
            spy_norm = 100 * (spy_price / rsp_price)
            spread = ((spy_norm - rsp_norm) / rsp_norm) * 100
        else:
            spread = ((spy_price - rsp_price) / rsp_price) * 100

        return spread

    @staticmethod
    def calculate_historical_spread(
        rsp_history: pd.DataFrame,
        spy_history: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate historical RSP vs SPY spread

        Args:
            rsp_history: DataFrame with RSP prices (must have 'Close' column)
            spy_history: DataFrame with SPY prices (must have 'Close' column)

        Returns:
            DataFrame with spread values
        """
        try:
            # Align dates
            common_dates = rsp_history.index.intersection(spy_history.index)

            if len(common_dates) < 20:
                logger.warning("Insufficient data for spread calculation")
                return pd.DataFrame()

            rsp_prices = rsp_history.loc[common_dates, 'Close']
            spy_prices = spy_history.loc[common_dates, 'Close']

            # Normalize both to 100 at start
            rsp_norm = (rsp_prices / rsp_prices.iloc[0]) * 100
            spy_norm = (spy_prices / spy_prices.iloc[0]) * 100

            # Calculate spread
            spread = ((spy_norm - rsp_norm) / rsp_norm) * 100

            spread_df = pd.DataFrame({
                'date': common_dates,
                'rsp_price': rsp_prices,
                'spy_price': spy_prices,
                'rsp_normalized': rsp_norm,
                'spy_normalized': spy_norm,
                'spread': spread
            })

            spread_df.set_index('date', inplace=True)

            return spread_df

        except Exception as e:
            logger.error(f"Error calculating historical spread: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_spread_statistics(spread_history: pd.DataFrame) -> dict:
        """
        Calculate statistics for RSP vs SPY spread

        Args:
            spread_history: DataFrame with 'spread' column

        Returns:
            Dict with spread statistics
        """
        if spread_history.empty or 'spread' not in spread_history.columns:
            return {}

        spread = spread_history['spread']

        return {
            'current': spread.iloc[-1],
            'mean': spread.mean(),
            'median': spread.median(),
            'std': spread.std(),
            'min': spread.min(),
            'max': spread.max(),
            'percentile_25': spread.quantile(0.25),
            'percentile_75': spread.quantile(0.75),
            'percentile_90': spread.quantile(0.90),
            'z_score': (spread.iloc[-1] - spread.mean()) / spread.std() if spread.std() > 0 else 0
        }

    @staticmethod
    def is_spread_at_extreme(
        current_spread: float,
        threshold: float = 8.0,
        direction: str = "positive"
    ) -> Tuple[bool, dict]:
        """
        Check if spread is at extreme levels (trigger point)

        Args:
            current_spread: Current spread percentage
            threshold: Threshold for extreme (default 8%)
            direction: 'positive' or 'negative'

        Returns:
            (is_extreme, details)
        """
        if direction == "positive":
            is_extreme = current_spread >= threshold
        else:
            is_extreme = current_spread <= -threshold

        details = {
            'current_spread': current_spread,
            'threshold': threshold,
            'is_extreme': is_extreme,
            'distance_from_threshold': abs(current_spread - threshold)
        }

        return is_extreme, details

    @staticmethod
    def calculate_reversion_probability(
        spread_history: pd.DataFrame,
        current_spread: float,
        lookback_days: int = 252
    ) -> float:
        """
        Estimate probability of mean reversion based on historical data

        Args:
            spread_history: DataFrame with spread history
            current_spread: Current spread value
            lookback_days: Days to look back for historical analysis

        Returns:
            Probability (0-100) that spread will revert
        """
        if spread_history.empty or len(spread_history) < lookback_days:
            return 50.0  # Default to 50% if insufficient data

        try:
            # Get recent history
            recent = spread_history.tail(lookback_days)
            spread = recent['spread']

            # Calculate mean and std
            mean = spread.mean()
            std = spread.std()

            # Calculate z-score
            z_score = (current_spread - mean) / std if std > 0 else 0

            # Historical reversion rate
            # Find instances where spread was at similar extreme
            similar_extremes = spread[abs(spread - current_spread) < std * 0.5]

            if len(similar_extremes) < 5:
                # Not enough data, use z-score based estimate
                # Higher z-score = higher probability of reversion
                prob = min(50 + abs(z_score) * 10, 95)
            else:
                # Calculate how often it reverted
                reversions = 0
                for idx in similar_extremes.index:
                    # Look ahead 20 days
                    future_idx = spread.index.get_loc(idx) + 20
                    if future_idx < len(spread):
                        future_spread = spread.iloc[future_idx]
                        # Did it move toward mean?
                        if current_spread > mean and future_spread < current_spread:
                            reversions += 1
                        elif current_spread < mean and future_spread > current_spread:
                            reversions += 1

                prob = (reversions / len(similar_extremes)) * 100

            return min(max(prob, 30), 95)  # Clamp between 30% and 95%

        except Exception as e:
            logger.error(f"Error calculating reversion probability: {e}")
            return 50.0

    @staticmethod
    def get_sector_rotation_signal(
        spread_stats: dict,
        threshold: float = 8.0
    ) -> dict:
        """
        Generate sector rotation signal based on spread

        Args:
            spread_stats: Output from get_spread_statistics()
            threshold: Spread threshold for signal

        Returns:
            Dict with signal details
        """
        current = spread_stats.get('current', 0)
        z_score = spread_stats.get('z_score', 0)

        if current >= threshold:
            signal = "STRONG_ROTATION"
            description = "Equal-weight underperforming significantly - strong rotation opportunity"
            confidence = min(50 + abs(z_score) * 15, 95)
        elif current >= threshold * 0.8:
            signal = "MODERATE_ROTATION"
            description = "Equal-weight underperforming - rotation setup developing"
            confidence = min(50 + abs(z_score) * 10, 80)
        elif current <= -threshold:
            signal = "REVERSE_ROTATION"
            description = "Equal-weight outperforming - potential reversal"
            confidence = min(50 + abs(z_score) * 15, 95)
        else:
            signal = "NEUTRAL"
            description = "No significant rotation signal"
            confidence = 50

        return {
            'signal': signal,
            'description': description,
            'confidence': confidence,
            'current_spread': current,
            'z_score': z_score
        }

    @staticmethod
    def calculate_equal_weight_vs_cap_weight_performance(
        rsp_history: pd.DataFrame,
        spy_history: pd.DataFrame,
        start_date: Optional[datetime] = None
    ) -> dict:
        """
        Calculate cumulative performance comparison

        Args:
            rsp_history: RSP price history
            spy_history: SPY price history
            start_date: Start date for comparison

        Returns:
            Dict with performance metrics
        """
        try:
            if start_date:
                rsp_history = rsp_history[rsp_history.index >= start_date]
                spy_history = spy_history[spy_history.index >= start_date]

            # Align dates
            common_dates = rsp_history.index.intersection(spy_history.index)
            rsp_prices = rsp_history.loc[common_dates, 'Close']
            spy_prices = spy_history.loc[common_dates, 'Close']

            # Calculate returns
            rsp_return = ((rsp_prices.iloc[-1] - rsp_prices.iloc[0]) / rsp_prices.iloc[0]) * 100
            spy_return = ((spy_prices.iloc[-1] - spy_prices.iloc[0]) / spy_prices.iloc[0]) * 100

            # Calculate annualized returns
            years = len(common_dates) / 252
            rsp_annualized = ((1 + rsp_return/100) ** (1/years) - 1) * 100 if years > 0 else 0
            spy_annualized = ((1 + spy_return/100) ** (1/years) - 1) * 100 if years > 0 else 0

            return {
                'rsp_total_return': rsp_return,
                'spy_total_return': spy_return,
                'rsp_annualized': rsp_annualized,
                'spy_annualized': spy_annualized,
                'outperformance': rsp_return - spy_return,
                'start_date': common_dates[0],
                'end_date': common_dates[-1],
                'years': years
            }

        except Exception as e:
            logger.error(f"Error calculating performance: {e}")
            return {}
