"""
Reversion Hunter - Options Scanner Dashboard
Main Streamlit Application
"""
import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Reversion Hunter - Options Scanner",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        padding-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .alert-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .success-box {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

def main():
    """Main application"""

    # Sidebar
    with st.sidebar:
        st.markdown("## 🎯 Reversion Hunter")
        st.markdown("---")

        st.markdown("### Navigation")
        st.markdown("""
        - **Scanner**: Find de-concentration opportunities
        - **Alerts**: Configure notifications
        - **Positions**: Track open trades
        - **Backtest**: Historical performance
        - **Education**: Learn the strategy
        """)

        st.markdown("---")

        st.markdown("### Settings")

        # Portfolio configuration
        portfolio_size = st.number_input(
            "Portfolio Size ($)",
            min_value=10000,
            max_value=10000000,
            value=100000,
            step=10000,
            help="Total portfolio capital"
        )

        max_position_size = st.slider(
            "Max Position Size (%)",
            min_value=1.0,
            max_value=10.0,
            value=2.5,
            step=0.5,
            help="Maximum % of portfolio per trade"
        )

        min_ev = st.slider(
            "Min Expected Value (%)",
            min_value=10,
            max_value=50,
            value=20,
            step=5,
            help="Minimum expected value to trigger alert"
        )

        st.markdown("---")

        # Store in session state
        st.session_state['portfolio_size'] = portfolio_size
        st.session_state['max_position_size'] = max_position_size
        st.session_state['min_ev'] = min_ev / 100

        # API Status
        st.markdown("### API Status")
        check_api_status()

    # Main content
    st.markdown('<div class="main-header">🎯 REVERSION HUNTER</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">De-Concentration Options Scanner - 70-80% Win Rate Strategy</div>', unsafe_allow_html=True)

    # Welcome message
    st.markdown("""
    ## Welcome to Reversion Hunter

    This scanner identifies **high-probability options trades** during market de-concentration periods when
    equal-weight indices (RSP) underperform cap-weighted indices (SPY).

    ### The Strategy

    **Multi-Layer Screening System:**

    1. **Layer 1: Fundamentals** - Identify undervalued quality stocks
       - P/E Ratio: 8-15x
       - Market Cap: >$10B
       - ROE: >12%
       - Low correlation to Mag 7

    2. **Layer 2: Mean Reversion** - Find entry triggers
       - RSP vs SPY spread: >8% divergence
       - RSI: 30-45 (oversold but stable)
       - Volume: Above average

    3. **Layer 3: Greeks** - Optimize spreads
       - Put Spreads: 80-85% win rate (Delta 0.15-0.20)
       - Call Spreads: 60-70% win rate (Delta 0.60-0.70)
       - High theta, low gamma, optimal IV

    4. **Layer 4: Risk Management** - Position sizing
       - Expected Value: >20%
       - Position size: 2-5% of portfolio
       - Sector diversification

    ### Target Performance

    - **Win Rate**: 70-85% across 1,000+ trades
    - **Expected Returns**: 100-300% over time
    - **Risk Management**: Systematic stops and profit targets

    ### Get Started

    Navigate to **📊 Scanner** in the sidebar to find opportunities!
    """)

    # Quick stats
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Portfolio Size",
            value=f"${portfolio_size:,.0f}",
        )

    with col2:
        st.metric(
            label="Max Position Size",
            value=f"{max_position_size}%",
            delta=f"${portfolio_size * max_position_size / 100:,.0f}"
        )

    with col3:
        st.metric(
            label="Min Expected Value",
            value=f"{min_ev}%"
        )

    with col4:
        st.metric(
            label="Max Positions",
            value="15"
        )


def check_api_status():
    """Check API status"""
    from src.data.yahoo_finance import YahooFinanceClient

    if 'api_status_checked' not in st.session_state:
        with st.spinner("Checking APIs..."):
            yf_client = YahooFinanceClient()
            yf_status = yf_client.health_check()

        st.session_state['yf_status'] = yf_status
        st.session_state['api_status_checked'] = True

    # Display status
    if st.session_state.get('yf_status', False):
        st.success("✅ Yahoo Finance: OK")
    else:
        st.error("❌ Yahoo Finance: Error")

    # Check for API keys
    alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    if alpha_vantage_key and alpha_vantage_key != 'your_alpha_vantage_key_here':
        st.success("✅ Alpha Vantage: Configured")
    else:
        st.warning("⚠️ Alpha Vantage: Not configured")


if __name__ == "__main__":
    main()
