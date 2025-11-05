"""
Yahoo Finance API client for stock and options data
"""
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from .api_client import BaseAPIClient, cached
from ..models.stock import StockFundamentals, StockTechnicals
from ..models.option import OptionContract, OptionType

logger = logging.getLogger(__name__)


class YahooFinanceClient(BaseAPIClient):
    """Yahoo Finance data client (free tier)"""

    def __init__(self, cache_enabled: bool = True):
        super().__init__(
            api_key=None,  # Yahoo Finance doesn't require API key
            cache_enabled=cache_enabled,
            cache_ttl=900,  # 15 minutes
            rate_limit=2000  # Very generous
        )

    def health_check(self) -> bool:
        """Check if Yahoo Finance is accessible"""
        try:
            ticker = yf.Ticker("SPY")
            info = ticker.info
            return 'symbol' in info or 'shortName' in info
        except Exception as e:
            logger.error(f"Yahoo Finance health check failed: {e}")
            return False

    @cached(ttl=900)
    def get_stock_fundamentals(self, symbol: str) -> Optional[StockFundamentals]:
        """Fetch fundamental data for a stock"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Calculate EPS growth
            eps_current = info.get('trailingEps')
            # Note: Yahoo doesn't provide quarterly EPS easily
            # We'll use annual growth as proxy
            eps_growth = info.get('earningsQuarterlyGrowth')

            fundamentals = StockFundamentals(
                symbol=symbol,
                company_name=info.get('longName', symbol),
                current_price=info.get('currentPrice', info.get('regularMarketPrice', 0)),
                market_cap=info.get('marketCap', 0),
                pe_ratio=info.get('trailingPE'),
                forward_pe=info.get('forwardPE'),
                peg_ratio=info.get('pegRatio'),
                roe=info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else None,
                profit_margin=info.get('profitMargins', 0) * 100 if info.get('profitMargins') else None,
                operating_margin=info.get('operatingMargins', 0) * 100 if info.get('operatingMargins') else None,
                debt_to_equity=info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else None,
                current_ratio=info.get('currentRatio'),
                quick_ratio=info.get('quickRatio'),
                eps_current=eps_current,
                revenue_growth=info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else None,
                earnings_growth=eps_growth * 100 if eps_growth else None,
                sector=info.get('sector'),
                industry=info.get('industry'),
                beta=info.get('beta'),
                avg_volume=info.get('averageVolume'),
                volume=info.get('volume'),
                week_52_high=info.get('fiftyTwoWeekHigh'),
                week_52_low=info.get('fiftyTwoWeekLow'),
            )

            logger.info(f"Fetched fundamentals for {symbol}")
            return fundamentals

        except Exception as e:
            logger.error(f"Error fetching fundamentals for {symbol}: {e}")
            return None

    @cached(ttl=300)
    def get_stock_technicals(self, symbol: str, period: str = "3mo") -> Optional[StockTechnicals]:
        """Fetch technical indicators for a stock"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)

            if hist.empty:
                return None

            # Calculate technical indicators
            current_price = hist['Close'].iloc[-1]
            volume = hist['Volume'].iloc[-1]

            # Moving averages
            sma_20 = hist['Close'].rolling(window=20).mean().iloc[-1]
            sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1] if len(hist) >= 50 else None
            sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1] if len(hist) >= 200 else None

            # RSI calculation
            rsi = self._calculate_rsi(hist['Close'])

            # Volume metrics
            avg_volume_20d = hist['Volume'].rolling(window=20).mean().iloc[-1]
            volume_ratio = volume / avg_volume_20d if avg_volume_20d > 0 else None

            # ATR calculation
            atr = self._calculate_atr(hist)

            # 52-week low distance
            week_52_low = hist['Close'].min()
            distance_from_52w_low = ((current_price - week_52_low) / week_52_low * 100) if week_52_low > 0 else None

            technicals = StockTechnicals(
                symbol=symbol,
                current_price=current_price,
                sma_20=sma_20,
                sma_50=sma_50,
                sma_200=sma_200,
                rsi=rsi,
                rsi_14=rsi,
                atr=atr,
                volume=volume,
                avg_volume_20d=avg_volume_20d,
                volume_ratio=volume_ratio,
                distance_from_52w_low=distance_from_52w_low,
            )

            logger.info(f"Fetched technicals for {symbol}")
            return technicals

        except Exception as e:
            logger.error(f"Error fetching technicals for {symbol}: {e}")
            return None

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> Optional[float]:
        """Calculate RSI (Relative Strength Index)"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1]
        except Exception:
            return None

    def _calculate_atr(self, hist: pd.DataFrame, period: int = 14) -> Optional[float]:
        """Calculate Average True Range"""
        try:
            high = hist['High']
            low = hist['Low']
            close = hist['Close']

            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())

            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean().iloc[-1]
            return atr
        except Exception:
            return None

    @cached(ttl=300)
    def get_options_chain(self, symbol: str, expiration: Optional[str] = None) -> dict:
        """
        Fetch options chain for a symbol

        Args:
            symbol: Stock ticker
            expiration: Specific expiration date (YYYY-MM-DD) or None for all

        Returns:
            Dict with 'calls' and 'puts' DataFrames
        """
        try:
            ticker = yf.Ticker(symbol)

            if expiration:
                options = ticker.option_chain(expiration)
            else:
                # Get nearest expiration
                expirations = ticker.options
                if not expirations:
                    return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}
                options = ticker.option_chain(expirations[0])

            logger.info(f"Fetched options chain for {symbol}")
            return {
                'calls': options.calls,
                'puts': options.puts
            }

        except Exception as e:
            logger.error(f"Error fetching options for {symbol}: {e}")
            return {'calls': pd.DataFrame(), 'puts': pd.DataFrame()}

    def get_available_expirations(self, symbol: str) -> List[str]:
        """Get list of available option expiration dates"""
        try:
            ticker = yf.Ticker(symbol)
            return list(ticker.options)
        except Exception as e:
            logger.error(f"Error fetching expirations for {symbol}: {e}")
            return []

    def get_option_contracts(
        self,
        symbol: str,
        expiration: str,
        option_type: OptionType = OptionType.PUT
    ) -> List[OptionContract]:
        """Get list of option contracts"""
        try:
            chain = self.get_options_chain(symbol, expiration)
            df = chain['puts'] if option_type == OptionType.PUT else chain['calls']

            if df.empty:
                return []

            contracts = []
            exp_date = datetime.strptime(expiration, '%Y-%m-%d').date()

            for _, row in df.iterrows():
                try:
                    contract = OptionContract(
                        symbol=symbol,
                        strike=row['strike'],
                        expiration=exp_date,
                        option_type=option_type,
                        bid=row.get('bid'),
                        ask=row.get('ask'),
                        last=row.get('lastPrice'),
                        mark=(row.get('bid', 0) + row.get('ask', 0)) / 2 if row.get('bid') and row.get('ask') else None,
                        volume=row.get('volume'),
                        open_interest=row.get('openInterest'),
                        implied_volatility=row.get('impliedVolatility'),
                        contract_symbol=row.get('contractSymbol'),
                    )
                    contracts.append(contract)
                except Exception as e:
                    logger.debug(f"Skipping contract: {e}")
                    continue

            return contracts

        except Exception as e:
            logger.error(f"Error parsing option contracts for {symbol}: {e}")
            return []

    @cached(ttl=3600)
    def get_historical_prices(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        period: str = "1y"
    ) -> pd.DataFrame:
        """Get historical price data"""
        try:
            ticker = yf.Ticker(symbol)

            if start_date and end_date:
                hist = ticker.history(start=start_date, end=end_date)
            else:
                hist = ticker.history(period=period)

            return hist

        except Exception as e:
            logger.error(f"Error fetching historical prices for {symbol}: {e}")
            return pd.DataFrame()

    def calculate_correlation(
        self,
        symbol: str,
        benchmark: str = "SPY",
        period: str = "6mo"
    ) -> Optional[float]:
        """Calculate correlation between stock and benchmark"""
        try:
            # Get historical data
            stock_hist = self.get_historical_prices(symbol, period=period)
            bench_hist = self.get_historical_prices(benchmark, period=period)

            if stock_hist.empty or bench_hist.empty:
                return None

            # Calculate returns
            stock_returns = stock_hist['Close'].pct_change().dropna()
            bench_returns = bench_hist['Close'].pct_change().dropna()

            # Align dates
            common_dates = stock_returns.index.intersection(bench_returns.index)
            if len(common_dates) < 20:
                return None

            stock_returns = stock_returns.loc[common_dates]
            bench_returns = bench_returns.loc[common_dates]

            # Calculate correlation
            correlation = stock_returns.corr(bench_returns)
            return correlation

        except Exception as e:
            logger.error(f"Error calculating correlation for {symbol}: {e}")
            return None

    def calculate_mag7_correlation(self, symbol: str, period: str = "6mo") -> Optional[float]:
        """
        Calculate correlation to Magnificent 7 stocks
        (AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA)
        """
        try:
            mag7_symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA']

            stock_hist = self.get_historical_prices(symbol, period=period)
            if stock_hist.empty:
                return None

            stock_returns = stock_hist['Close'].pct_change().dropna()

            # Get Mag7 returns
            mag7_returns = []
            for mag7_symbol in mag7_symbols:
                hist = self.get_historical_prices(mag7_symbol, period=period)
                if not hist.empty:
                    returns = hist['Close'].pct_change().dropna()
                    mag7_returns.append(returns)

            if not mag7_returns:
                return None

            # Create Mag7 index (equal weighted)
            mag7_df = pd.concat(mag7_returns, axis=1)
            mag7_index = mag7_df.mean(axis=1)

            # Align dates
            common_dates = stock_returns.index.intersection(mag7_index.index)
            if len(common_dates) < 20:
                return None

            stock_returns = stock_returns.loc[common_dates]
            mag7_index = mag7_index.loc[common_dates]

            # Calculate correlation
            correlation = stock_returns.corr(mag7_index)
            return correlation

        except Exception as e:
            logger.error(f"Error calculating Mag7 correlation for {symbol}: {e}")
            return None
