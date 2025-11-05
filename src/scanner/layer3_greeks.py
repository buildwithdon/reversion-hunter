"""
Layer 3: Options Greeks Analysis Scanner
Find optimal option spreads based on Greeks criteria
"""
from typing import List, Optional, Tuple, Union
from datetime import datetime, timedelta, date
import logging

from ..data.yahoo_finance import YahooFinanceClient
from ..models.stock import Stock
from ..models.option import OptionContract, OptionType, PutSpread, CallSpread
from ..calculations.greeks import GreeksCalculator

logger = logging.getLogger(__name__)


class GreeksScanner:
    """
    Layer 3: Analyze options and find optimal spreads based on Greeks

    For PUT SPREADS (bullish/neutral):
    - Delta: 0.15-0.20 on short put
    - Theta: >0.05 per day
    - IV Percentile: >67%
    - Vega: Positive
    - Gamma: Low (<0.05)
    - DTE: 30-45 days
    - Strike Width: $5-10
    - Premium/Width Ratio: >15%

    For CALL SPREADS (aggressive bullish):
    - Delta: 0.60-0.70 on long call
    - Theta: Acceptable (<-0.03/day)
    - IV Percentile: 30-50%
    - DTE: 60-90 days
    - Strike Width: $5-10
    - Risk/Reward: >2:1
    """

    def __init__(
        self,
        data_client: Optional[YahooFinanceClient] = None,
        risk_free_rate: float = 0.05
    ):
        self.data_client = data_client or YahooFinanceClient()
        self.greeks_calc = GreeksCalculator()
        self.risk_free_rate = risk_free_rate

    def scan_put_spreads(
        self,
        stock: Stock,
        dte_range: Tuple[int, int] = (30, 45)
    ) -> List[PutSpread]:
        """
        Find optimal put credit spreads for a stock

        Args:
            stock: Stock object that passed Layer 1 & 2
            dte_range: Days to expiration range (min, max)

        Returns:
            List of PutSpread objects that meet criteria
        """
        if not stock.fundamentals:
            return []

        spreads = []
        current_price = stock.fundamentals.current_price

        try:
            # Get available expirations
            expirations = self.data_client.get_available_expirations(stock.symbol)
            if not expirations:
                logger.warning(f"No options available for {stock.symbol}")
                return []

            # Filter expirations by DTE
            valid_expirations = self._filter_expirations_by_dte(expirations, dte_range)

            for expiration_str in valid_expirations:
                # Get put contracts for this expiration
                put_contracts = self._get_put_contracts_with_greeks(
                    stock.symbol,
                    expiration_str,
                    current_price
                )

                if len(put_contracts) < 2:
                    continue

                # Find spreads that meet criteria
                expiration_spreads = self._build_put_spreads(
                    put_contracts,
                    current_price,
                    stock.symbol
                )

                spreads.extend(expiration_spreads)

            # Filter spreads that pass Layer 3 criteria
            passing_spreads = [s for s in spreads if s.passes_layer3_criteria()[0]]

            logger.info(f"Found {len(passing_spreads)} put spreads for {stock.symbol}")
            return passing_spreads

        except Exception as e:
            logger.error(f"Error scanning put spreads for {stock.symbol}: {e}")
            return []

    def scan_call_spreads(
        self,
        stock: Stock,
        dte_range: Tuple[int, int] = (60, 90)
    ) -> List[CallSpread]:
        """
        Find optimal call debit spreads for a stock

        Args:
            stock: Stock object that passed Layer 1 & 2
            dte_range: Days to expiration range (min, max)

        Returns:
            List of CallSpread objects that meet criteria
        """
        if not stock.fundamentals:
            return []

        spreads = []
        current_price = stock.fundamentals.current_price

        try:
            # Get available expirations
            expirations = self.data_client.get_available_expirations(stock.symbol)
            if not expirations:
                return []

            # Filter expirations by DTE
            valid_expirations = self._filter_expirations_by_dte(expirations, dte_range)

            for expiration_str in valid_expirations:
                # Get call contracts for this expiration
                call_contracts = self._get_call_contracts_with_greeks(
                    stock.symbol,
                    expiration_str,
                    current_price
                )

                if len(call_contracts) < 2:
                    continue

                # Find spreads that meet criteria
                expiration_spreads = self._build_call_spreads(
                    call_contracts,
                    current_price,
                    stock.symbol
                )

                spreads.extend(expiration_spreads)

            # Filter spreads that pass Layer 3 criteria
            passing_spreads = [s for s in spreads if s.passes_layer3_criteria()[0]]

            logger.info(f"Found {len(passing_spreads)} call spreads for {stock.symbol}")
            return passing_spreads

        except Exception as e:
            logger.error(f"Error scanning call spreads for {stock.symbol}: {e}")
            return []

    def _filter_expirations_by_dte(
        self,
        expirations: List[str],
        dte_range: Tuple[int, int]
    ) -> List[str]:
        """Filter expirations by days-to-expiration range"""
        valid_exps = []
        today = date.today()

        for exp_str in expirations:
            try:
                exp_date = datetime.strptime(exp_str, '%Y-%m-%d').date()
                dte = (exp_date - today).days

                if dte_range[0] <= dte <= dte_range[1]:
                    valid_exps.append(exp_str)
            except Exception:
                continue

        return valid_exps

    def _get_put_contracts_with_greeks(
        self,
        symbol: str,
        expiration: str,
        current_price: float
    ) -> List[OptionContract]:
        """Get put contracts and calculate Greeks"""
        contracts = self.data_client.get_option_contracts(
            symbol,
            expiration,
            OptionType.PUT
        )

        # Calculate Greeks for each contract
        exp_date = datetime.strptime(expiration, '%Y-%m-%d').date()
        dte_years = self.greeks_calc.years_to_expiration(exp_date)

        for contract in contracts:
            if contract.implied_volatility and contract.implied_volatility > 0:
                greeks = self.greeks_calc.calculate_all_greeks(
                    spot_price=current_price,
                    strike_price=contract.strike,
                    time_to_expiration=dte_years,
                    risk_free_rate=self.risk_free_rate,
                    implied_volatility=contract.implied_volatility,
                    option_type="put"
                )

                contract.delta = greeks['delta']
                contract.gamma = greeks['gamma']
                contract.theta = greeks['theta']
                contract.vega = greeks['vega']
                contract.rho = greeks['rho']

        return contracts

    def _get_call_contracts_with_greeks(
        self,
        symbol: str,
        expiration: str,
        current_price: float
    ) -> List[OptionContract]:
        """Get call contracts and calculate Greeks"""
        contracts = self.data_client.get_option_contracts(
            symbol,
            expiration,
            OptionType.CALL
        )

        # Calculate Greeks for each contract
        exp_date = datetime.strptime(expiration, '%Y-%m-%d').date()
        dte_years = self.greeks_calc.years_to_expiration(exp_date)

        for contract in contracts:
            if contract.implied_volatility and contract.implied_volatility > 0:
                greeks = self.greeks_calc.calculate_all_greeks(
                    spot_price=current_price,
                    strike_price=contract.strike,
                    time_to_expiration=dte_years,
                    risk_free_rate=self.risk_free_rate,
                    implied_volatility=contract.implied_volatility,
                    option_type="call"
                )

                contract.delta = greeks['delta']
                contract.gamma = greeks['gamma']
                contract.theta = greeks['theta']
                contract.vega = greeks['vega']
                contract.rho = greeks['rho']

        return contracts

    def _build_put_spreads(
        self,
        put_contracts: List[OptionContract],
        current_price: float,
        symbol: str
    ) -> List[PutSpread]:
        """Build put spreads from available contracts"""
        spreads = []

        # Filter for potential short puts (delta -0.15 to -0.20)
        short_put_candidates = [
            c for c in put_contracts
            if c.delta is not None
            and -0.20 <= c.delta <= -0.15
            and c.strike < current_price  # OTM
            and c.bid is not None
            and c.ask is not None
        ]

        for short_put in short_put_candidates:
            # Find long puts (protection) $5-10 below
            long_put_candidates = [
                c for c in put_contracts
                if c.strike < short_put.strike
                and 5 <= (short_put.strike - c.strike) <= 10
                and c.bid is not None
                and c.ask is not None
            ]

            for long_put in long_put_candidates:
                try:
                    # Calculate net premium
                    short_premium = (short_put.bid + short_put.ask) / 2
                    long_premium = (long_put.bid + long_put.ask) / 2
                    net_premium = short_premium - long_premium

                    if net_premium <= 0:
                        continue

                    # Create spread
                    spread = PutSpread(
                        symbol=symbol,
                        short_put=short_put,
                        long_put=long_put,
                        net_premium_collected=net_premium,
                        dte=short_put.days_to_expiration or 0
                    )

                    spreads.append(spread)

                except Exception as e:
                    logger.debug(f"Error building put spread: {e}")
                    continue

        return spreads

    def _build_call_spreads(
        self,
        call_contracts: List[OptionContract],
        current_price: float,
        symbol: str
    ) -> List[CallSpread]:
        """Build call spreads from available contracts"""
        spreads = []

        # Filter for potential long calls (delta 0.60-0.70)
        long_call_candidates = [
            c for c in call_contracts
            if c.delta is not None
            and 0.60 <= c.delta <= 0.70
            and c.strike <= current_price * 1.05  # ATM to slightly ITM
            and c.bid is not None
            and c.ask is not None
        ]

        for long_call in long_call_candidates:
            # Find short calls (cap) $5-10 above
            short_call_candidates = [
                c for c in call_contracts
                if c.strike > long_call.strike
                and 5 <= (c.strike - long_call.strike) <= 10
                and c.bid is not None
                and c.ask is not None
            ]

            for short_call in short_call_candidates:
                try:
                    # Calculate net debit
                    long_premium = (long_call.bid + long_call.ask) / 2
                    short_premium = (short_call.bid + short_call.ask) / 2
                    net_debit = long_premium - short_premium

                    if net_debit <= 0:
                        continue

                    # Create spread
                    spread = CallSpread(
                        symbol=symbol,
                        long_call=long_call,
                        short_call=short_call,
                        net_debit_paid=net_debit,
                        dte=long_call.days_to_expiration or 0
                    )

                    spreads.append(spread)

                except Exception as e:
                    logger.debug(f"Error building call spread: {e}")
                    continue

        return spreads

    def rank_spreads_by_quality(
        self,
        spreads: List[Union[PutSpread, CallSpread]]
    ) -> List[Union[PutSpread, CallSpread]]:
        """
        Rank spreads by overall quality

        Ranking criteria:
        - Higher probability of profit
        - Better premium/width ratio (for put spreads)
        - Better risk/reward (for call spreads)
        - Higher theta (for put spreads)
        - Lower gamma
        """
        def quality_score(spread: Union[PutSpread, CallSpread]) -> float:
            score = 0

            # Probability of profit (0-100)
            if spread.probability_of_profit:
                score += spread.probability_of_profit * 0.4

            if isinstance(spread, PutSpread):
                # Premium/width ratio
                ratio = spread.premium_to_width_ratio()
                score += min(ratio / 25 * 100, 100) * 0.3

                # Theta (higher is better)
                if spread.theta:
                    theta_score = min(spread.theta / 0.10 * 100, 100)
                    score += theta_score * 0.2
            else:  # CallSpread
                # Risk/reward ratio
                rr = spread.risk_reward_ratio()
                score += min(rr / 3 * 100, 100) * 0.3

                # Theta (less negative is better)
                if spread.theta:
                    theta_score = max(0, (0.03 + spread.theta) / 0.03 * 100)
                    score += theta_score * 0.2

            # Gamma (lower is better)
            if spread.gamma:
                gamma_score = max(0, (0.05 - abs(spread.gamma)) / 0.05 * 100)
                score += gamma_score * 0.1

            return score

        return sorted(spreads, key=quality_score, reverse=True)
