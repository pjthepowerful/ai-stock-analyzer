# 🚀 Quick Start Guide - Avoiding Rate Limits

## Common Issue: "Too Many Requests" Error

Yahoo Finance limits how many requests you can make. Here's how to avoid issues:

### ✅ Best Practices

1. **Wait Between Analyses**
   - Wait 1-2 minutes between analyzing different stocks
   - The app caches data for 10 minutes, so re-analyzing the same stock is instant

2. **Use the App Efficiently**
   - Start with Stock Analysis for 1-2 stocks
   - Use Watchlist to monitor favorites (data is cached)
   - Run Stock Screener only when needed (it queries 35+ stocks)

3. **If You Hit the Limit**
   - Wait 5-10 minutes
   - Clear your browser cache (Ctrl+F5)
   - Restart the Streamlit app: `Ctrl+C` then `streamlit run stock_analyzer.py`

### 🎯 Recommended Workflow

**For Quick Analysis:**
```
1. Enter ticker (e.g., AAPL)
2. Click Analyze
3. Wait 30 seconds before analyzing another stock
```

**For Multiple Stocks:**
```
1. Add to Watchlist (sidebar)
2. Watchlist uses cached data
3. Analyze individual stocks from there
```

**For Screening:**
```
1. Use Stock Screener sparingly (once per session)
2. Export results to CSV
3. Analyze interesting picks individually
```

### 🔧 Technical Solutions Implemented

The app now includes:
- ✅ **Smart Caching**: 10-minute cache to reduce API calls
- ✅ **Retry Logic**: Automatic retries with delays
- ✅ **Rate Limit Detection**: Warns you when hit
- ✅ **Delayed Requests**: 500ms between stocks in screener
- ✅ **Graceful Fallbacks**: Continues working even if some data fails

### 💡 Pro Tips

1. **Use Popular Tickers**: AAPL, MSFT, GOOGL have more reliable data
2. **Avoid Exotic Tickers**: Penny stocks may have incomplete data
3. **Peak Hours**: Yahoo Finance is slower during US market hours (9:30 AM - 4 PM ET)
4. **Cache is Your Friend**: Re-running same analysis is instant due to caching

### 🐛 Troubleshooting

**Error: "Rate limited. Try after a while."**
- Solution: Wait 5 minutes, then try again

**Error: "Invalid ticker or no data available"**
- Check ticker symbol is correct
- Try on Yahoo Finance website to verify it exists

**App is slow**
- Clear cache: Press `C` in the Streamlit interface
- Restart app: `Ctrl+C` then rerun

**Screener times out**
- It analyzes 35+ stocks, which takes time
- Use filters to narrow results
- Consider running during off-peak hours

### 📊 Data Freshness

- **Real-time quote**: Updated when you analyze
- **Historical data**: Last 10 minutes cached
- **Company info**: Cached for 10 minutes
- **Screener results**: Run manually when needed

### 🎓 Learning Mode

If you're just learning, try:
1. Pick 3-5 favorite stocks
2. Add them to your watchlist
3. Analyze them once per day
4. Track their AI scores over time

This approach avoids rate limits and helps you learn patterns!

---

**Remember**: This tool uses free Yahoo Finance data. For professional trading, consider paid data providers with higher rate limits.
