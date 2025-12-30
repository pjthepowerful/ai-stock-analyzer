# Add this to your imports section at the top
import anthropic
import json
import os

# Add 'Chatbot' to your navigation in the sidebar section
# Replace the Navigation section with this:

st.markdown("#### Navigation")
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("🔍 Scanner", use_container_width=True):
        st.session_state.page = 'Scanner'
        st.rerun()
with col2:
    if st.button("📊 Analyze", use_container_width=True):
        st.session_state.page = 'Individual'
        st.rerun()
with col3:
    if st.button("💰 Sizer", use_container_width=True):
        st.session_state.page = 'Position Sizer'
        st.rerun()
with col4:
    if st.button("💬 Chat", use_container_width=True):
        st.session_state.page = 'Chatbot'
        st.rerun()

# Add these new session state initializations with your other session state code
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []
if 'anthropic_client' not in st.session_state:
    st.session_state.anthropic_client = None

# Add these tool/function wrapper definitions before your page routing
# (put this after all your existing functions but before the page selection)

def scan_stock_tool(ticker, timeframe='1d'):
    """Wrapper for chatbot to scan individual stocks"""
    try:
        period = '6mo' if timeframe == '1d' else '2mo'
        hist, info = get_stock_data_optimized(ticker, period=period, interval=timeframe)
        
        if hist.empty or len(hist) < 60:
            return {
                "success": False,
                "error": f"Unable to fetch sufficient data for {ticker}"
            }
        
        hist = calculate_swing_indicators(hist)
        setup_type, quality, entry, stop, target, reason = identify_setup_type(hist, info)
        
        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2]
        change_pct = ((current_price - prev_close) / prev_close) * 100
        
        if setup_type:
            shares, position_value = calculate_position_size(
                st.session_state.account_size,
                st.session_state.risk_per_trade,
                entry,
                stop
            )
            risk_amount = st.session_state.account_size * (st.session_state.risk_per_trade / 100)
            potential_profit = shares * (target - entry)
            reward_risk_ratio = (target - entry) / (entry - stop) if entry > stop else 0
            
            return {
                "success": True,
                "ticker": ticker,
                "current_price": round(current_price, 2),
                "price_change_pct": round(change_pct, 2),
                "setup_type": setup_type,
                "quality": quality,
                "entry": round(entry, 2),
                "stop": round(stop, 2),
                "target": round(target, 2),
                "reason": reason,
                "rsi": round(hist['RSI'].iloc[-1], 1),
                "volume_ratio": round(hist['Volume_Ratio'].iloc[-1], 1),
                "shares": shares,
                "position_value": round(position_value, 2),
                "risk_amount": round(risk_amount, 2),
                "potential_profit": round(potential_profit, 2),
                "reward_risk_ratio": round(reward_risk_ratio, 2)
            }
        else:
            return {
                "success": False,
                "ticker": ticker,
                "current_price": round(current_price, 2),
                "price_change_pct": round(change_pct, 2),
                "error": f"No valid setup found: {reason}",
                "rsi": round(hist['RSI'].iloc[-1], 1),
                "volume_ratio": round(hist['Volume_Ratio'].iloc[-1], 1)
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error analyzing {ticker}: {str(e)}"
        }

def scan_nasdaq_tool(timeframe='1d', top_n=20, min_quality=70):
    """Wrapper for chatbot to scan Nasdaq 100"""
    try:
        results_df, regime, strength = scan_nasdaq_for_setups(
            timeframe=timeframe,
            top_n=top_n,
            min_quality=min_quality
        )
        
        if results_df.empty:
            return {
                "success": False,
                "market_regime": regime,
                "market_strength": round(strength, 2),
                "message": "No setups found meeting criteria"
            }
        
        # Convert dataframe to list of dicts for easier JSON handling
        setups = []
        for _, row in results_df.iterrows():
            setups.append({
                "ticker": row['Ticker'],
                "setup": row['Setup'],
                "quality": row['Quality'],
                "entry": round(row['Entry'], 2),
                "stop": round(row['Stop'], 2),
                "target": round(row['Target'], 2),
                "r_r_ratio": round(row['R_R_Ratio'], 2),
                "shares": row['Shares'],
                "position_value": round(row['Position_$'], 2),
                "rsi": round(row['RSI'], 1),
                "volume_ratio": round(row['Volume_Ratio'], 1),
                "reason": row['Reason']
            })
        
        return {
            "success": True,
            "market_regime": regime,
            "market_strength": round(strength, 2),
            "total_setups": len(setups),
            "setups": setups
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error scanning Nasdaq: {str(e)}"
        }

def calculate_position_tool(entry, stop, target=None, account_size=None, risk_percent=None):
    """Wrapper for position sizing calculator"""
    try:
        acc_size = account_size if account_size else st.session_state.account_size
        risk_pct = risk_percent if risk_percent else st.session_state.risk_per_trade
        
        if entry <= stop:
            return {
                "success": False,
                "error": "Entry price must be greater than stop loss"
            }
        
        shares, position_value = calculate_position_size(acc_size, risk_pct, entry, stop)
        risk_amount = acc_size * (risk_pct / 100)
        risk_per_share = entry - stop
        
        result = {
            "success": True,
            "shares": shares,
            "position_value": round(position_value, 2),
            "risk_amount": round(risk_amount, 2),
            "risk_per_share": round(risk_per_share, 2),
            "portfolio_pct": round((position_value / acc_size) * 100, 2),
            "account_size": acc_size,
            "risk_percent": risk_pct
        }
        
        if target:
            reward_per_share = target - entry
            potential_profit = shares * reward_per_share
            reward_risk_ratio = reward_per_share / risk_per_share
            
            result.update({
                "target": round(target, 2),
                "potential_profit": round(potential_profit, 2),
                "reward_risk_ratio": round(reward_risk_ratio, 2),
                "reward_per_share": round(reward_per_share, 2)
            })
        
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Error calculating position: {str(e)}"
        }

def get_market_regime_tool():
    """Wrapper for market regime check"""
    try:
        regime, strength = get_market_regime()
        return {
            "success": True,
            "regime": regime,
            "strength": round(strength, 2),
            "description": {
                "BULLISH": "Market is in a strong uptrend. Good environment for swing trading.",
                "NEUTRAL_BULLISH": "Market is above 200 SMA but not strongly trending. Trade with caution.",
                "BEARISH": "Market is in a downtrend. Cash is a position.",
                "NEUTRAL": "Market is choppy. Wait for clearer direction."
            }.get(regime, "Unknown market condition")
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error checking market regime: {str(e)}"
        }

def process_chatbot_message(user_message, conversation_history):
    """Main chatbot processing function using Claude API with tool use"""
    
    # Initialize Anthropic client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "⚠️ Please set your ANTHROPIC_API_KEY environment variable to use the chatbot."
    
    if not st.session_state.anthropic_client:
        st.session_state.anthropic_client = anthropic.Anthropic(api_key=api_key)
    
    client = st.session_state.anthropic_client
    
    # Define tools for Claude
    tools = [
        {
            "name": "scan_stock",
            "description": "Scan an individual stock ticker for swing trading setups. Returns setup type, quality score, entry/stop/target prices, position sizing, and technical indicators.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol (e.g., AAPL, TSLA, NVDA)"
                    },
                    "timeframe": {
                        "type": "string",
                        "enum": ["1d", "1h"],
                        "description": "Chart timeframe - '1d' for daily or '1h' for hourly",
                        "default": "1d"
                    }
                },
                "required": ["ticker"]
            }
        },
        {
            "name": "scan_nasdaq_100",
            "description": "Scan all Nasdaq 100 stocks for high-quality swing trading setups. Returns top setups ranked by quality score with complete trade plans.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "timeframe": {
                        "type": "string",
                        "enum": ["1d", "1h"],
                        "description": "Chart timeframe",
                        "default": "1d"
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Maximum number of setups to return",
                        "default": 20,
                        "minimum": 5,
                        "maximum": 30
                    },
                    "min_quality": {
                        "type": "integer",
                        "description": "Minimum quality score (60-90)",
                        "default": 70,
                        "minimum": 60,
                        "maximum": 90
                    }
                },
                "required": []
            }
        },
        {
            "name": "calculate_position_size",
            "description": "Calculate optimal position size and risk/reward metrics for a trade based on entry, stop loss, and optional target prices.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "entry": {
                        "type": "number",
                        "description": "Entry price"
                    },
                    "stop": {
                        "type": "number",
                        "description": "Stop loss price"
                    },
                    "target": {
                        "type": "number",
                        "description": "Target price (optional)"
                    },
                    "account_size": {
                        "type": "number",
                        "description": "Account size in dollars (uses user's default if not provided)"
                    },
                    "risk_percent": {
                        "type": "number",
                        "description": "Risk percentage per trade (uses user's default if not provided)"
                    }
                },
                "required": ["entry", "stop"]
            }
        },
        {
            "name": "get_market_regime",
            "description": "Check the current market regime (BULLISH, NEUTRAL_BULLISH, BEARISH, or NEUTRAL) based on QQQ's position relative to moving averages.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    ]
    
    system_prompt = f"""You are a professional swing trading assistant with deep expertise in technical analysis and risk management. You help traders analyze stocks, find high-quality setups, and manage positions using a proven institutional strategy.

**Your Trading System:**
- Only trade stocks in confirmed uptrends (price > 50 SMA > 200 SMA)
- Focus on 5 high-probability setup types:
  1. EMA 20 Pullback (highest probability)
  2. SMA 50 Pullback (major support)
  3. Consolidation Breakout (momentum plays)
  4. Support Bounce (strong stocks only)
  5. Mean Reversion (oversold recovery in uptrends)
  
- Quality scoring: 85-100 (exceptional), 75-84 (strong), 65-74 (good), <65 (filtered out)
- Strict risk management: Fixed percentage risk per trade
- Only trade in bullish market regimes

**User's Current Settings:**
- Account Size: ${st.session_state.account_size:,}
- Risk Per Trade: {st.session_state.risk_per_trade}%
- Risk Amount: ${st.session_state.account_size * (st.session_state.risk_per_trade / 100):,.0f} per trade

**Your Capabilities:**
You have access to tools that can:
- Scan individual stocks for setups
- Scan entire Nasdaq 100 for opportunities
- Calculate position sizes with risk/reward metrics
- Check market regime conditions

**Communication Style:**
- Be professional but conversational
- Explain setups clearly with supporting technical reasons
- Always emphasize risk management
- Provide actionable trade plans when setups exist
- Be honest when no good setups are available
- Use emojis sparingly for emphasis (🔥 for strong setups, ⚠️ for warnings, ✅ for good setups)

**Critical Reminders:**
- This is educational content, not financial advice
- Always remind users to verify data before trading
- Never guarantee profits or downplay risks
- Encourage proper position sizing and stop losses

When a user asks you to scan stocks or analyze anything, use your tools to get real data, then provide a clear, actionable response."""

    # Build messages array with conversation history
    messages = []
    for msg in conversation_history:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    # Add current user message
    messages.append({
        "role": "user",
        "content": user_message
    })
    
    # Conversation loop with tool use
    max_iterations = 5
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                tools=tools,
                messages=messages
            )
            
            # Check if Claude wants to use tools
            if response.stop_reason == "tool_use":
                # Process all tool uses in the response
                assistant_content = []
                tool_results = []
                
                for block in response.content:
                    if block.type == "text":
                        assistant_content.append(block)
                    elif block.type == "tool_use":
                        # Execute the appropriate tool
                        tool_name = block.name
                        tool_input = block.input
                        
                        if tool_name == "scan_stock":
                            result = scan_stock_tool(
                                ticker=tool_input["ticker"],
                                timeframe=tool_input.get("timeframe", "1d")
                            )
                        elif tool_name == "scan_nasdaq_100":
                            result = scan_nasdaq_tool(
                                timeframe=tool_input.get("timeframe", "1d"),
                                top_n=tool_input.get("top_n", 20),
                                min_quality=tool_input.get("min_quality", 70)
                            )
                        elif tool_name == "calculate_position_size":
                            result = calculate_position_tool(
                                entry=tool_input["entry"],
                                stop=tool_input["stop"],
                                target=tool_input.get("target"),
                                account_size=tool_input.get("account_size"),
                                risk_percent=tool_input.get("risk_percent")
                            )
                        elif tool_name == "get_market_regime":
                            result = get_market_regime_tool()
                        else:
                            result = {"error": f"Unknown tool: {tool_name}"}
                        
                        # Store tool use and result
                        assistant_content.append(block)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result)
                        })
                
                # Add assistant message with tool uses
                messages.append({
                    "role": "assistant",
                    "content": assistant_content
                })
                
                # Add tool results
                messages.append({
                    "role": "user",
                    "content": tool_results
                })
                
                # Continue loop to get final response
                continue
            
            else:
                # Final text response
                final_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        final_text += block.text
                
                return final_text
                
        except Exception as e:
            return f"❌ Error communicating with AI: {str(e)}\n\nPlease check your API key and try again."
    
    return "⚠️ Response took too long. Please try a simpler question."

# Now add the Chatbot page section (add this with your other page sections)

elif page == 'Chatbot':
    st.title("💬 AI Trading Assistant")
    st.markdown("Ask me anything about stocks, setups, position sizing, or market conditions!")
    
    # API Key check
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        st.error("⚠️ Anthropic API Key not found!")
        st.markdown("""
        To use the chatbot, you need to set your Anthropic API key as an environment variable:
        
        **Option 1: Command Line (Temporary)**
```bash
        export ANTHROPIC_API_KEY='your-api-key-here'
        streamlit run your_app.py
```
        
        **Option 2: .env file (Recommended)**
        1. Create a `.env` file in your project directory
        2. Add: `ANTHROPIC_API_KEY=your-api-key-here`
        3. Install python-dotenv: `pip install python-dotenv`
        4. Add to top of your script:
```python
        from dotenv import load_dotenv
        load_dotenv()
```
        
        Get your API key at: https://console.anthropic.com/
        """)
        st.stop()
    
    # Quick action buttons
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔍 Scan Nasdaq 100", use_container_width=True):
            st.session_state.chat_messages.append({
                "role": "user",
                "content": "Scan the Nasdaq 100 for the best swing trading setups"
            })
            st.rerun()
    
    with col2:
        if st.button("📊 Market Regime", use_container_width=True):
            st.session_state.chat_messages.append({
                "role": "user",
                "content": "What's the current market regime?"
            })
            st.rerun()
    
    with col3:
        if st.button("🎯 Best Setups", use_container_width=True):
            st.session_state.chat_messages.append({
                "role": "user",
                "content": "Show me only the highest quality setups (85+ score)"
            })
            st.rerun()
    
    with col4:
        if st.button("🧹 Clear Chat", use_container_width=True):
            st.session_state.chat_messages = []
            st.rerun()
    
    st.markdown("---")
    
    # Display chat messages
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask about stocks, setups, or trading strategy..."):
        # Add user message to chat
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                response = process_chatbot_message(prompt, st.session_state.chat_messages[:-1])
            st.markdown(response)
        
        # Add assistant response to chat
        st.session_state.chat_messages.append({"role": "assistant", "content": response})
        
        # Rerun to update chat
        st.rerun()
    
    # Example queries
    if len(st.session_state.chat_messages) == 0:
        st.markdown("### 💡 Example Questions")
        st.markdown("""
        - "Scan the Nasdaq 100"
        - "Analyze AAPL for swing trading setups"
        - "What's the current market regime?"
        - "Show me high-quality setups with 80+ score"
        - "Calculate position size for TSLA entry at $250, stop at $242"
        - "Scan for EMA 20 pullback setups only"
        - "What are the best stocks to trade today?"
        - "Explain the EMA 20 pullback strategy"
        """)
