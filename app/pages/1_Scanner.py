"""
Scanner Page - Main options screening dashboard
"""
import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.data.yahoo_finance import YahooFinanceClient
from src.scanner.layer1_fundamentals import FundamentalsScanner
from src.scanner.layer2_mean_reversion import MeanReversionScanner
from src.scanner.layer3_greeks import GreeksScanner
from src.scanner.layer4_risk_management import RiskManagementScanner

st.set_page_config(page_title="Scanner", page_icon="📊", layout="wide")

st.title("📊 Options Scanner")
st.markdown("Find high-probability de-concentration opportunities")

# Initialize session state
if 'scan_complete' not in st.session_state:
    st.session_state.scan_complete = False
if 'trade_signals' not in st.session_state:
    st.session_state.trade_signals = []

# Get settings from main app
portfolio_size = st.session_state.get('portfolio_size', 100000)
max_position_size = st.session_state.get('max_position_size', 2.5)
min_ev = st.session_state.get('min_ev', 0.20)

# Scanner configuration
st.sidebar.markdown("## Scanner Configuration")

scan_mode = st.sidebar.radio(
    "Scan Mode",
    ["Quick Scan (Top 20)", "Full Scan (All Sectors)", "Custom Universe"],
    help="Quick scan checks 20 top stocks, full scan checks all"
)

if scan_mode == "Custom Universe":
    custom_symbols = st.sidebar.text_area(
        "Enter symbols (comma-separated)",
        value="JPM,BAC,UNH,JNJ,PG,KO",
        help="Enter ticker symbols separated by commas"
    )
    universe = [s.strip().upper() for s in custom_symbols.split(",")]
else:
    universe = None  # Will use default

spread_type = st.sidebar.selectbox(
    "Spread Type",
    ["Put Spreads (80-85% Win Rate)", "Call Spreads (60-70% Win Rate)", "Both"],
    help="Type of spreads to search for"
)

scan_put_spreads = spread_type in ["Put Spreads (80-85% Win Rate)", "Both"]
scan_call_spreads = spread_type in ["Call Spreads (60-70% Win Rate)", "Both"]

# RSP vs SPY Spread Monitor
st.markdown("## 📈 Market Trigger: RSP vs SPY Spread")

col1, col2 = st.columns([2, 1])

with col1:
    # Display RSP/SPY spread
    if st.button("🔄 Refresh RSP/SPY Spread", type="primary"):
        with st.spinner("Calculating RSP vs SPY spread..."):
            try:
                data_client = YahooFinanceClient()
                mean_rev_scanner = MeanReversionScanner(data_client)
                spread_data = mean_rev_scanner.get_rsp_spy_spread()

                if spread_data:
                    st.session_state['rsp_spy_spread'] = spread_data
                else:
                    st.error("Could not calculate RSP/SPY spread")
            except Exception as e:
                st.error(f"Error calculating spread: {e}")

    if 'rsp_spy_spread' in st.session_state:
        spread_data = st.session_state['rsp_spy_spread']
        stats = spread_data.get('spread_stats', {})
        current_spread = stats.get('current', 0)
        is_extreme = spread_data.get('is_extreme', False)
        rotation_signal = spread_data.get('rotation_signal', {})

        # Display current spread
        if is_extreme:
            st.success(f"🎯 **TRIGGER ACTIVE!** Current spread: **{current_spread:.2f}%** (Threshold: 8%)")
        else:
            st.info(f"Current spread: **{current_spread:.2f}%** (Threshold: 8%)")

        # Display rotation signal
        signal_type = rotation_signal.get('signal', 'NEUTRAL')
        description = rotation_signal.get('description', '')
        confidence = rotation_signal.get('confidence', 0)

        if signal_type == "STRONG_ROTATION":
            st.markdown(f"""
            <div class="success-box">
            <strong>Signal:</strong> {signal_type}<br>
            <strong>Confidence:</strong> {confidence:.1f}%<br>
            <strong>Analysis:</strong> {description}
            </div>
            """, unsafe_allow_html=True)
        elif signal_type == "MODERATE_ROTATION":
            st.markdown(f"""
            <div class="alert-box">
            <strong>Signal:</strong> {signal_type}<br>
            <strong>Confidence:</strong> {confidence:.1f}%<br>
            <strong>Analysis:</strong> {description}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"**Signal:** {signal_type} - {description}")

with col2:
    if 'rsp_spy_spread' in st.session_state:
        stats = st.session_state['rsp_spy_spread'].get('spread_stats', {})

        st.metric("Mean", f"{stats.get('mean', 0):.2f}%")
        st.metric("Std Dev", f"{stats.get('std', 0):.2f}%")
        st.metric("Z-Score", f"{stats.get('z_score', 0):.2f}")
        st.metric("Reversion Prob", f"{st.session_state['rsp_spy_spread'].get('reversion_probability', 50):.1f}%")

# Run Scanner
st.markdown("---")
st.markdown("## 🔍 Run Multi-Layer Scanner")

if st.button("🚀 START SCAN", type="primary", use_container_width=True):
    with st.spinner("Running multi-layer scanner..."):
        try:
            # Initialize clients and scanners
            data_client = YahooFinanceClient()

            layer1_scanner = FundamentalsScanner(data_client)
            layer2_scanner = MeanReversionScanner(data_client)
            layer3_scanner = GreeksScanner(data_client)
            layer4_scanner = RiskManagementScanner(
                portfolio_size=portfolio_size,
                max_position_size_percent=max_position_size,
                min_expected_value=min_ev
            )

            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Layer 1: Fundamentals
            status_text.text("Layer 1: Scanning fundamentals...")
            if universe:
                symbols_to_scan = universe
            elif scan_mode == "Quick Scan (Top 20)":
                symbols_to_scan = layer1_scanner.get_default_universe()[:20]
            else:
                symbols_to_scan = layer1_scanner.get_default_universe()

            layer1_stocks = []
            for i, symbol in enumerate(symbols_to_scan):
                stock = layer1_scanner.scan_symbol(symbol)
                if stock and stock.layer1_pass:
                    layer1_stocks.append(stock)
                progress_bar.progress((i + 1) / len(symbols_to_scan) * 0.25)

            st.session_state['layer1_stocks'] = layer1_stocks
            status_text.text(f"Layer 1: {len(layer1_stocks)}/{len(symbols_to_scan)} passed")

            # Layer 2: Mean Reversion
            status_text.text("Layer 2: Analyzing technical triggers...")
            layer2_stocks = layer2_scanner.scan_stocks(layer1_stocks)
            layer2_stocks = layer2_scanner.rank_by_mean_reversion_strength(layer2_stocks)

            st.session_state['layer2_stocks'] = layer2_stocks
            progress_bar.progress(0.50)
            status_text.text(f"Layer 2: {len(layer2_stocks)}/{len(layer1_stocks)} passed")

            # Layer 3: Greeks Analysis
            status_text.text("Layer 3: Scanning options and calculating Greeks...")
            all_spreads = {}
            stocks_by_symbol = {s.symbol: s for s in layer2_stocks}

            for i, stock in enumerate(layer2_stocks[:10]):  # Limit to top 10 to save time
                spreads = []

                if scan_put_spreads:
                    put_spreads = layer3_scanner.scan_put_spreads(stock)
                    spreads.extend(put_spreads)

                if scan_call_spreads:
                    call_spreads = layer3_scanner.scan_call_spreads(stock)
                    spreads.extend(call_spreads)

                if spreads:
                    ranked_spreads = layer3_scanner.rank_spreads_by_quality(spreads)
                    all_spreads[stock.symbol] = ranked_spreads

                progress_bar.progress(0.50 + (i + 1) / min(len(layer2_stocks), 10) * 0.25)

            st.session_state['layer3_spreads'] = all_spreads
            status_text.text(f"Layer 3: Found spreads for {len(all_spreads)} stocks")

            # Layer 4: Risk Management
            status_text.text("Layer 4: Validating risk management...")
            rsp_spy_spread = st.session_state.get('rsp_spy_spread', {}).get('spread_stats', {}).get('current')

            trade_signals = layer4_scanner.scan_spreads(
                all_spreads,
                stocks_by_symbol,
                rsp_spy_spread
            )

            # Rank and filter
            trade_signals = layer4_scanner.rank_trade_signals(trade_signals)
            trade_signals = layer4_scanner.filter_by_sector_limits(
                trade_signals,
                stocks_by_symbol
            )

            st.session_state['trade_signals'] = trade_signals[:15]  # Top 15
            st.session_state['stocks_by_symbol'] = stocks_by_symbol
            st.session_state['scan_complete'] = True

            progress_bar.progress(1.0)
            status_text.text(f"✅ Scan complete! Found {len(trade_signals)} trade signals")

            st.success(f"🎉 Found {len(trade_signals)} high-probability trade opportunities!")

        except Exception as e:
            st.error(f"Error during scan: {e}")
            import traceback
            st.code(traceback.format_exc())

# Display Results
if st.session_state.get('scan_complete', False):
    st.markdown("---")
    st.markdown("## 🎯 Trade Signals")

    trade_signals = st.session_state.get('trade_signals', [])
    stocks_by_symbol = st.session_state.get('stocks_by_symbol', {})

    if trade_signals:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Trade Signals", len(trade_signals))

        with col2:
            avg_ev = sum(t.expected_value for t in trade_signals) / len(trade_signals)
            st.metric("Avg Expected Value", f"{avg_ev*100:.1f}%")

        with col3:
            avg_pop = sum(t.probability_of_profit for t in trade_signals) / len(trade_signals)
            st.metric("Avg Win Rate", f"{avg_pop:.1f}%")

        with col4:
            total_capital = sum(t.capital_at_risk for t in trade_signals)
            st.metric("Total Capital at Risk", f"${total_capital:,.0f}")

        # Display trades
        st.markdown("### Top Trade Opportunities")

        for i, trade in enumerate(trade_signals, 1):
            stock = stocks_by_symbol.get(trade.symbol)

            with st.expander(f"#{i} - {trade.symbol} - {trade.spread_type.value} - EV: {trade.expected_value*100:.1f}% - PoP: {trade.probability_of_profit:.1f}%"):
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Stock Analysis**")
                    if stock and stock.fundamentals:
                        st.write(f"- **Company:** {stock.fundamentals.company_name}")
                        st.write(f"- **Sector:** {stock.fundamentals.sector}")
                        st.write(f"- **Price:** ${stock.fundamentals.current_price:.2f}")
                        st.write(f"- **P/E Ratio:** {stock.fundamentals.pe_ratio:.2f}")
                        st.write(f"- **ROE:** {stock.fundamentals.roe:.1f}%")
                        st.write(f"- **Debt/Equity:** {stock.fundamentals.debt_to_equity:.2f}")

                    if stock and stock.technicals:
                        st.markdown("**Technical Indicators**")
                        st.write(f"- **RSI:** {stock.technicals.rsi:.1f}")
                        st.write(f"- **Volume Ratio:** {stock.technicals.volume_ratio:.2f}x")
                        st.write(f"- **Distance from 52w Low:** {stock.technicals.distance_from_52w_low:.1f}%")

                with col2:
                    st.markdown("**Trade Setup**")
                    st.write(f"- **Type:** {trade.spread_type.value}")
                    st.write(f"- **Entry Price:** ${trade.entry_price:.2f}")
                    st.write(f"- **Capital at Risk:** ${trade.capital_at_risk:,.0f}")
                    st.write(f"- **Take Profit:** ${trade.take_profit:,.0f}")
                    st.write(f"- **Stop Loss:** ${trade.stop_loss:,.0f}")
                    st.write(f"- **Expected Value:** {trade.expected_value*100:.1f}%")
                    st.write(f"- **Probability of Profit:** {trade.probability_of_profit:.1f}%")
                    st.write(f"- **DTE:** {trade.spread.dte} days")

                    if hasattr(trade.spread, 'short_put'):
                        st.markdown("**Put Spread Details**")
                        st.write(f"- **Short Put Strike:** ${trade.spread.short_put.strike}")
                        st.write(f"- **Long Put Strike:** ${trade.spread.long_put.strike}")
                        st.write(f"- **Strike Width:** ${trade.spread.strike_width}")
                        st.write(f"- **Premium Collected:** ${trade.spread.net_premium_collected:.2f}")
                    elif hasattr(trade.spread, 'long_call'):
                        st.markdown("**Call Spread Details**")
                        st.write(f"- **Long Call Strike:** ${trade.spread.long_call.strike}")
                        st.write(f"- **Short Call Strike:** ${trade.spread.short_call.strike}")
                        st.write(f"- **Strike Width:** ${trade.spread.strike_width}")
                        st.write(f"- **Debit Paid:** ${trade.spread.net_debit_paid:.2f}")

                st.markdown("**Entry Notes**")
                st.info(trade.entry_notes)

        # Export to CSV
        st.markdown("---")
        if st.button("📥 Export Trade Signals to CSV"):
            trade_data = []
            for trade in trade_signals:
                stock = stocks_by_symbol.get(trade.symbol)
                trade_data.append({
                    'Symbol': trade.symbol,
                    'Type': trade.spread_type.value,
                    'Entry Price': trade.entry_price,
                    'Capital at Risk': trade.capital_at_risk,
                    'Expected Value %': trade.expected_value * 100,
                    'Probability of Profit %': trade.probability_of_profit,
                    'DTE': trade.spread.dte,
                    'Sector': stock.fundamentals.sector if stock and stock.fundamentals else 'N/A',
                    'Entry Notes': trade.entry_notes
                })

            df = pd.DataFrame(trade_data)
            csv = df.to_csv(index=False)

            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"reversion_hunter_signals_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

    else:
        st.info("No trade signals found meeting all criteria. Try adjusting scanner settings.")
