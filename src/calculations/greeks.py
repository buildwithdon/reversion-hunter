"""
Options Greeks calculations using Black-Scholes model
"""
import numpy as np
from scipy.stats import norm
from typing import Tuple
from datetime import date
import logging

logger = logging.getLogger(__name__)


class GreeksCalculator:
    """Calculate Options Greeks using Black-Scholes model"""

    @staticmethod
    def calculate_all_greeks(
        spot_price: float,
        strike_price: float,
        time_to_expiration: float,  # in years
        risk_free_rate: float,
        implied_volatility: float,
        option_type: str = "call"
    ) -> dict:
        """
        Calculate all Greeks for an option

        Args:
            spot_price: Current stock price
            strike_price: Strike price of option
            time_to_expiration: Time to expiration in years
            risk_free_rate: Risk-free interest rate (as decimal, e.g., 0.05 for 5%)
            implied_volatility: Implied volatility (as decimal, e.g., 0.25 for 25%)
            option_type: 'call' or 'put'

        Returns:
            Dict with delta, gamma, theta, vega, rho
        """
        try:
            if time_to_expiration <= 0:
                # Option has expired
                if option_type.lower() == "call":
                    delta = 1.0 if spot_price > strike_price else 0.0
                else:
                    delta = -1.0 if spot_price < strike_price else 0.0
                return {
                    'delta': delta,
                    'gamma': 0.0,
                    'theta': 0.0,
                    'vega': 0.0,
                    'rho': 0.0
                }

            # Calculate d1 and d2
            d1 = (np.log(spot_price / strike_price) +
                  (risk_free_rate + 0.5 * implied_volatility ** 2) * time_to_expiration) / \
                 (implied_volatility * np.sqrt(time_to_expiration))

            d2 = d1 - implied_volatility * np.sqrt(time_to_expiration)

            # Calculate Greeks
            if option_type.lower() == "call":
                delta = norm.cdf(d1)
                theta = (-spot_price * norm.pdf(d1) * implied_volatility / (2 * np.sqrt(time_to_expiration)) -
                         risk_free_rate * strike_price * np.exp(-risk_free_rate * time_to_expiration) * norm.cdf(d2))
                rho = strike_price * time_to_expiration * np.exp(-risk_free_rate * time_to_expiration) * norm.cdf(d2) / 100
            else:  # put
                delta = norm.cdf(d1) - 1
                theta = (-spot_price * norm.pdf(d1) * implied_volatility / (2 * np.sqrt(time_to_expiration)) +
                         risk_free_rate * strike_price * np.exp(-risk_free_rate * time_to_expiration) * norm.cdf(-d2))
                rho = -strike_price * time_to_expiration * np.exp(-risk_free_rate * time_to_expiration) * norm.cdf(-d2) / 100

            # Gamma and Vega are same for calls and puts
            gamma = norm.pdf(d1) / (spot_price * implied_volatility * np.sqrt(time_to_expiration))
            vega = spot_price * norm.pdf(d1) * np.sqrt(time_to_expiration) / 100  # Divide by 100 for 1% change

            # Theta is typically expressed per day
            theta = theta / 365

            return {
                'delta': delta,
                'gamma': gamma,
                'theta': theta,
                'vega': vega,
                'rho': rho
            }

        except Exception as e:
            logger.error(f"Error calculating Greeks: {e}")
            return {
                'delta': None,
                'gamma': None,
                'theta': None,
                'vega': None,
                'rho': None
            }

    @staticmethod
    def calculate_delta(
        spot_price: float,
        strike_price: float,
        time_to_expiration: float,
        risk_free_rate: float,
        implied_volatility: float,
        option_type: str = "call"
    ) -> float:
        """Calculate option delta"""
        greeks = GreeksCalculator.calculate_all_greeks(
            spot_price, strike_price, time_to_expiration,
            risk_free_rate, implied_volatility, option_type
        )
        return greeks['delta']

    @staticmethod
    def days_to_expiration(expiration_date: date) -> int:
        """Calculate days to expiration"""
        return (expiration_date - date.today()).days

    @staticmethod
    def years_to_expiration(expiration_date: date) -> float:
        """Calculate time to expiration in years"""
        days = GreeksCalculator.days_to_expiration(expiration_date)
        return days / 365.0

    @staticmethod
    def implied_volatility_percentile(
        current_iv: float,
        historical_ivs: list[float]
    ) -> float:
        """
        Calculate IV percentile rank

        Args:
            current_iv: Current implied volatility
            historical_ivs: List of historical IVs (typically 1 year)

        Returns:
            Percentile rank (0-100)
        """
        if not historical_ivs:
            return 50.0

        below_current = sum(1 for iv in historical_ivs if iv < current_iv)
        percentile = (below_current / len(historical_ivs)) * 100
        return percentile

    @staticmethod
    def black_scholes_price(
        spot_price: float,
        strike_price: float,
        time_to_expiration: float,
        risk_free_rate: float,
        implied_volatility: float,
        option_type: str = "call"
    ) -> float:
        """Calculate theoretical option price using Black-Scholes"""
        try:
            if time_to_expiration <= 0:
                if option_type.lower() == "call":
                    return max(spot_price - strike_price, 0)
                else:
                    return max(strike_price - spot_price, 0)

            d1 = (np.log(spot_price / strike_price) +
                  (risk_free_rate + 0.5 * implied_volatility ** 2) * time_to_expiration) / \
                 (implied_volatility * np.sqrt(time_to_expiration))

            d2 = d1 - implied_volatility * np.sqrt(time_to_expiration)

            if option_type.lower() == "call":
                price = (spot_price * norm.cdf(d1) -
                        strike_price * np.exp(-risk_free_rate * time_to_expiration) * norm.cdf(d2))
            else:  # put
                price = (strike_price * np.exp(-risk_free_rate * time_to_expiration) * norm.cdf(-d2) -
                        spot_price * norm.cdf(-d1))

            return price

        except Exception as e:
            logger.error(f"Error calculating Black-Scholes price: {e}")
            return 0.0

    @staticmethod
    def calculate_spread_greeks(
        long_greeks: dict,
        short_greeks: dict,
        is_credit_spread: bool = True
    ) -> dict:
        """
        Calculate net Greeks for a spread

        Args:
            long_greeks: Greeks for long option
            short_greeks: Greeks for short option
            is_credit_spread: True for credit spreads (selling), False for debit spreads

        Returns:
            Net Greeks for the spread
        """
        if is_credit_spread:
            # Credit spread: short option - long option (signs matter)
            return {
                'delta': -short_greeks['delta'] + long_greeks['delta'],
                'gamma': -short_greeks['gamma'] + long_greeks['gamma'],
                'theta': -short_greeks['theta'] + long_greeks['theta'],
                'vega': -short_greeks['vega'] + long_greeks['vega'],
                'rho': -short_greeks['rho'] + long_greeks['rho'],
            }
        else:
            # Debit spread: long option - short option
            return {
                'delta': long_greeks['delta'] - short_greeks['delta'],
                'gamma': long_greeks['gamma'] - short_greeks['gamma'],
                'theta': long_greeks['theta'] - short_greeks['theta'],
                'vega': long_greeks['vega'] - short_greeks['vega'],
                'rho': long_greeks['rho'] - short_greeks['rho'],
            }

    @staticmethod
    def probability_itm_from_delta(delta: float, option_type: str = "call") -> float:
        """
        Estimate probability of finishing in-the-money from delta

        For calls: delta ≈ probability ITM
        For puts: abs(delta) ≈ probability ITM
        """
        if option_type.lower() == "call":
            return delta * 100
        else:
            return abs(delta) * 100

    @staticmethod
    def probability_otm_from_delta(delta: float, option_type: str = "call") -> float:
        """
        Estimate probability of finishing out-of-the-money from delta
        """
        return 100 - GreeksCalculator.probability_itm_from_delta(delta, option_type)
