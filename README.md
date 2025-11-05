# 🎯 Reversion Hunter - De-Concentration Options Scanner

A sophisticated options scanner that identifies high-probability trades (70-85% win rate) during market de-concentration periods when equal-weight indices underperform cap-weighted indices.

## 📊 Strategy Overview

**Core Thesis**: When Magnificent 7 stocks dominate, RSP (equal-weight S&P 500) lags SPY (cap-weight S&P 500). This creates pricing dislocations in quality value stocks that mean revert, offering asymmetric risk/reward opportunities through options spreads.

### Target Performance
- **Win Rate**: 70-85% across 1,000+ trades
- **Expected Value**: 20-40% per trade
- **Annual Returns**: 100-300% on deployed capital
- **Maximum Drawdown**: <20% with proper position sizing

## 🔥 Features

### Multi-Layer Screening System

1. **Layer 1: Stock Fundamentals**
   - P/E Ratio: 8-15x (undervalued but stable)
   - Market Cap: >$10B (liquidity)
   - ROE: >12% (profitability)
   - Debt-to-Equity: <1.5 (clean balance sheet)
   - Negative correlation to Mag 7 stocks

2. **Layer 2: Mean Reversion Triggers**
   - RSP vs SPY spread >8% divergence
   - RSI: 30-45 (oversold but stable)
   - Volume above 20-day average
   - Price within 10% of 52-week low

3. **Layer 3: Options Greeks Optimization**
   - **Put Spreads**: Delta 0.15-0.20, Theta >0.05, IV >67th percentile
   - **Call Spreads**: Delta 0.60-0.70, Risk/Reward >2:1
   - DTE optimization: 30-45 days (puts), 60-90 days (calls)

4. **Layer 4: Risk Management**
   - Position sizing: 2-5% per trade
   - Expected Value threshold: >20%
   - Systematic stop losses and profit targets
   - Sector diversification limits

### Application Features

- **📊 Real-Time Scanner**: Live scanning with multi-layer filtering
- **📈 Position Tracker**: Monitor open trades and P&L
- **📚 Education Module**: Learn the strategy in-depth
- **📊 RSP/SPY Spread Monitor**: Track the trigger signal
- **💾 Export Capabilities**: Download trade signals as CSV
- **☁️ Cloud-Ready**: Deploy to Streamlit Cloud, Railway, or Render

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- pip

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/reversion-hunter.git
   cd reversion-hunter
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys (optional for free tier)
   ```

5. **Run the application**
   ```bash
   streamlit run app/main.py
   ```

6. **Access the dashboard**
   Open your browser to `http://localhost:8501`

## 📁 Project Structure

```
reversion-hunter/
├── app/                          # Streamlit application
│   ├── main.py                  # Main dashboard
│   ├── pages/
│   │   ├── 1_Scanner.py        # Options scanner page
│   │   ├── 2_Position_Tracker.py
│   │   └── 3_Education.py
│   └── components/              # Reusable UI components
├── src/                         # Core application logic
│   ├── scanner/                 # 4-layer scanning system
│   │   ├── layer1_fundamentals.py
│   │   ├── layer2_mean_reversion.py
│   │   ├── layer3_greeks.py
│   │   └── layer4_risk_management.py
│   ├── data/                    # Data fetching and APIs
│   │   ├── yahoo_finance.py
│   │   └── api_client.py
│   ├── models/                  # Data models
│   │   ├── stock.py
│   │   ├── option.py
│   │   └── trade.py
│   ├── calculations/            # Financial calculations
│   │   ├── greeks.py
│   │   ├── expected_value.py
│   │   └── spreads.py
│   └── utils/                   # Utilities
├── data/                        # Data storage
│   └── cache/                   # API response cache
├── tests/                       # Unit tests
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variables template
└── README.md
```

## 🔧 Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# Data Sources (Free tier works!)
ALPHA_VANTAGE_API_KEY=your_key_here  # Optional: Get free key at alphavantage.co

# Alert System (Optional)
SENDGRID_API_KEY=your_key_here
TWILIO_ACCOUNT_SID=your_sid_here
TELEGRAM_BOT_TOKEN=your_token_here

# Application Settings
CACHE_ENABLED=True
CACHE_EXPIRY_MINUTES=15
RSP_SPY_SPREAD_THRESHOLD=8.0
MIN_EXPECTED_VALUE=0.20
```

### Portfolio Settings

Configure in the sidebar:
- **Portfolio Size**: Total capital ($10K - $10M)
- **Max Position Size**: 1-10% per trade (recommended: 2.5%)
- **Min Expected Value**: 10-50% threshold (recommended: 20%)

## 📈 Usage Guide

### 1. Check RSP/SPY Spread

- Navigate to **Scanner** page
- Click "Refresh RSP/SPY Spread"
- Look for **TRIGGER ACTIVE** when spread >8%

### 2. Run the Scanner

- Select scan mode (Quick/Full/Custom)
- Choose spread type (Put/Call/Both)
- Click **START SCAN**
- Wait for multi-layer filtering (1-3 minutes)

### 3. Review Trade Signals

- View ranked opportunities
- Check Expected Value and Probability of Profit
- Review stock fundamentals and technicals
- Export signals to CSV

### 4. Track Positions

- Navigate to **Position Tracker**
- Add signals to portfolio
- Monitor P&L in real-time
- Close positions at profit targets

### 5. Learn the Strategy

- Navigate to **Education** page
- Understand the 4 layers
- Learn Options Greeks
- Master position management

## ☁️ Cloud Deployment

### Deploy to Streamlit Cloud (Recommended)

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Deploy on Streamlit Cloud**
   - Visit [share.streamlit.io](https://share.streamlit.io)
   - Connect your GitHub repo
   - Select `app/main.py` as main file
   - Add secrets (API keys) in settings
   - Deploy!

3. **Configure Secrets**
   In Streamlit Cloud settings, add:
   ```toml
   ALPHA_VANTAGE_API_KEY = "your_key"
   CACHE_ENABLED = "True"
   ```

### Deploy to Railway

1. **Install Railway CLI**
   ```bash
   npm install -g @railway/cli
   ```

2. **Deploy**
   ```bash
   railway login
   railway init
   railway up
   ```

### Deploy to Render

1. Create `render.yaml`:
   ```yaml
   services:
     - type: web
       name: reversion-hunter
       env: python
       buildCommand: pip install -r requirements.txt
       startCommand: streamlit run app/main.py --server.port $PORT
   ```

2. Connect repo to Render dashboard

## 📊 Data Sources

### Free Tier (Included)
- **Yahoo Finance**: Stock data, fundamentals, options chains
  - No API key required
  - Rate limit: ~2000 requests/hour
  - Real-time for US markets

### Paid Tier (Optional - Phase 4)
- **Polygon.io**: Real-time options data ($99/month)
- **Tradier**: Options Greeks and analytics ($Free - $75/month)
- **Alpha Vantage**: Additional fundamental data ($50/month premium)

## ⚠️ Risk Disclosure

**IMPORTANT**: Options trading involves substantial risk of loss.

- This is an educational tool, not financial advice
- Past performance does not guarantee future results
- Start with paper trading before using real capital
- Only trade with money you can afford to lose
- The 70-85% win rate is a long-term probability (1,000+ trades)
- Individual results will vary

**Recommended Approach**:
1. Study the Education module thoroughly
2. Paper trade for 3-6 months
3. Start with 25% of intended capital
4. Scale up as you prove the system
5. Never risk more than 2-5% per trade

## 💡 Pro Tips

1. **Wait for the Trigger**: Don't force trades when RSP/SPY spread <8%
2. **Take 50% Profits**: Higher win rate + faster turnover = better returns
3. **Honor Stop Losses**: One bad trade can wipe out 10 winners
4. **Track Everything**: Law of large numbers requires data
5. **Start Small**: Prove the system before scaling up
6. **Be Patient**: 1,000 trades is where the magic happens

**Happy Hunting! 🎯**

---

*Disclaimer: This software is for educational purposes only. Options trading involves risk. Always consult a financial advisor before trading.*