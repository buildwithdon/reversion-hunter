"""
Position Tracker - Monitor open trades and P&L
"""
import streamlit as st
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.models.trade import Trade, Portfolio, TradeStatus

st.set_page_config(page_title="Position Tracker", page_icon="📈", layout="wide")

st.title("📈 Position Tracker")
st.markdown("Monitor your open positions and track performance")

# Initialize portfolio in session state
if 'portfolio' not in st.session_state:
    portfolio_size = st.session_state.get('portfolio_size', 100000)
    max_position_size = st.session_state.get('max_position_size', 2.5)

    st.session_state['portfolio'] = Portfolio(
        total_capital=portfolio_size,
        max_position_size_percent=max_position_size,
        max_positions=15,
        max_sector_positions=3
    )

portfolio = st.session_state['portfolio']

# Portfolio Summary
st.markdown("## Portfolio Summary")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total Capital",
        f"${portfolio.total_capital:,.0f}"
    )

with col2:
    st.metric(
        "Open Positions",
        len(portfolio.open_trades),
        delta=f"{len(portfolio.open_trades)}/{portfolio.max_positions}"
    )

with col3:
    st.metric(
        "Total Realized P&L",
        f"${portfolio.total_realized_pnl:,.2f}",
        delta=f"{portfolio.total_return_percent:.1f}%"
    )

with col4:
    st.metric(
        "Win Rate",
        f"{portfolio.win_rate:.1f}%",
        delta=f"{portfolio.win_count}W / {portfolio.loss_count}L"
    )

# Add positions from scanner
st.markdown("---")
st.markdown("## Add Positions")

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("Add trade signals from the scanner to your portfolio:")

    trade_signals = st.session_state.get('trade_signals', [])
    if trade_signals:
        st.info(f"Found {len(trade_signals)} trade signals from last scan")

        if st.button("➕ Add All Trade Signals to Portfolio"):
            added = 0
            for trade in trade_signals:
                if len(portfolio.open_trades) < portfolio.max_positions:
                    trade.status = TradeStatus.OPEN
                    if portfolio.add_trade(trade):
                        added += 1

            st.success(f"Added {added} trades to portfolio!")
            st.rerun()
    else:
        st.info("Run the Scanner first to find trade opportunities")

with col2:
    st.markdown("**Portfolio Limits**")
    st.write(f"- Max Positions: {portfolio.max_positions}")
    st.write(f"- Max Sector: {portfolio.max_sector_positions}")
    st.write(f"- Max Position Size: {portfolio.max_position_size_percent}%")

# Open Positions
st.markdown("---")
st.markdown("## Open Positions")

if portfolio.open_trades:
    for i, trade in enumerate(portfolio.open_trades, 1):
        with st.expander(f"Position #{i}: {trade.symbol} - {trade.spread_type.value} - P&L: ${trade.unrealized_pnl or 0:.2f}"):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("**Trade Details**")
                st.write(f"Trade ID: {trade.trade_id}")
                st.write(f"Symbol: {trade.symbol}")
                st.write(f"Type: {trade.spread_type.value}")
                st.write(f"Entry Date: {trade.entry_date.strftime('%Y-%m-%d')}")
                st.write(f"Entry Price: ${trade.entry_price:.2f}")
                st.write(f"Days in Trade: {trade.days_in_trade()}")

            with col2:
                st.markdown("**P&L & Risk**")
                st.write(f"Current Price: ${trade.current_price:.2f}" if trade.current_price else "N/A")
                st.write(f"Unrealized P&L: ${trade.unrealized_pnl:.2f}" if trade.unrealized_pnl else "N/A")
                st.write(f"P&L %: {trade.pnl_percent:.1f}%" if trade.pnl_percent else "N/A")
                st.write(f"Capital at Risk: ${trade.capital_at_risk:,.0f}")
                st.write(f"Take Profit: ${trade.take_profit:,.0f}")
                st.write(f"Stop Loss: ${trade.stop_loss:,.0f}")

            with col3:
                st.markdown("**Probability Metrics**")
                st.write(f"Expected Value: {trade.expected_value*100:.1f}%")
                st.write(f"Probability of Profit: {trade.probability_of_profit:.1f}%")
                st.write(f"RSP/SPY at Entry: {trade.rsp_spy_spread_at_entry:.2f}%" if trade.rsp_spy_spread_at_entry else "N/A")

            # Action buttons
            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button(f"✅ Close at Profit", key=f"close_profit_{trade.trade_id}"):
                    # Simulate closing at 50% profit
                    exit_price = trade.entry_price * 0.5  # 50% of premium for put spreads
                    portfolio.close_trade(trade.trade_id, exit_price, "Closed at profit target")
                    st.success(f"Closed {trade.symbol} at profit!")
                    st.rerun()

            with col2:
                if st.button(f"❌ Close at Loss", key=f"close_loss_{trade.trade_id}"):
                    # Simulate closing at stop loss
                    exit_price = trade.entry_price * 2  # 2x premium for put spreads
                    portfolio.close_trade(trade.trade_id, exit_price, "Hit stop loss")
                    st.warning(f"Closed {trade.symbol} at stop loss")
                    st.rerun()

            with col3:
                if st.button(f"🔄 Update Price", key=f"update_{trade.trade_id}"):
                    # In production, fetch real-time price
                    # For now, simulate with random movement
                    import random
                    current_price = trade.entry_price * (1 + random.uniform(-0.3, 0.5))
                    trade.update_pnl(current_price)
                    st.info(f"Updated {trade.symbol}")
                    st.rerun()

else:
    st.info("No open positions. Add trades from the Scanner!")

# Closed Positions
st.markdown("---")
st.markdown("## Closed Positions")

if portfolio.closed_trades:
    # Create DataFrame
    closed_data = []
    for trade in portfolio.closed_trades:
        closed_data.append({
            'Symbol': trade.symbol,
            'Type': trade.spread_type.value,
            'Entry Date': trade.entry_date.strftime('%Y-%m-%d'),
            'Exit Date': trade.exit_date.strftime('%Y-%m-%d') if trade.exit_date else 'N/A',
            'Entry Price': f"${trade.entry_price:.2f}",
            'Exit Price': f"${trade.exit_price:.2f}" if trade.exit_price else 'N/A',
            'Realized P&L': f"${trade.realized_pnl:.2f}" if trade.realized_pnl else 'N/A',
            'P&L %': f"{trade.pnl_percent:.1f}%" if trade.pnl_percent else 'N/A',
            'Outcome': trade.outcome.value,
            'Days in Trade': trade.days_in_trade()
        })

    df = pd.DataFrame(closed_data)
    st.dataframe(df, use_container_width=True)

    # Download closed positions
    if st.button("📥 Export Closed Positions"):
        csv = df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"closed_positions_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
else:
    st.info("No closed positions yet")

# Performance Analytics
if portfolio.closed_trades:
    st.markdown("---")
    st.markdown("## Performance Analytics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Trades", len(portfolio.closed_trades))

    with col2:
        st.metric("Win Rate", f"{portfolio.win_rate:.1f}%")

    with col3:
        st.metric("Avg Win", f"${sum(t.realized_pnl for t in portfolio.closed_trades if t.outcome.value == 'win') / portfolio.win_count:.2f}" if portfolio.win_count > 0 else "N/A")

    with col4:
        st.metric("Avg Loss", f"${abs(sum(t.realized_pnl for t in portfolio.closed_trades if t.outcome.value == 'loss') / portfolio.loss_count):.2f}" if portfolio.loss_count > 0 else "N/A")
