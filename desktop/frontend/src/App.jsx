const send = async () => {
  const msg = input.trim()
  if (!msg || sending) return
  setMessages(prev => [...prev, { role: 'user', content: msg }])
  setInput('')
  setSending(true)

  try {
    const res = await fetch(`${API}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg })
    })
    const data = await res.json()

    if (data.ok) {
      const newMessage = {
        role: 'assistant',
        content: data.message,
        type: data.type || null,
        ticker: data.ticker || null,
        signal: data.trade_signal || null
      }

      setMessages(prev => [...prev, newMessage])

      // Update chat chart if message contains a ticker
      if (data.ticker) setChatChart({ ticker: data.ticker, signal: data.trade_signal || null })

      // Play appropriate sound
      if (data.type === 'trade') {
        if (data.message.includes('Bought')) playBuy()
        else if (data.message.includes('Sold') || data.message.includes('Shorted')) playSell()
        else if (data.message.includes('Covered')) playProfit()
        else playTick()
      } else playTick()

      if (data.autopilot !== undefined) setAutopilot(data.autopilot)
    } else {
      playAlert()
      setMessages(prev => [...prev, { role: 'assistant', content: `⚠️ ${data.error}` }])
    }

    refreshData()
  } catch (e) {
    setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Backend not connected' }])
  }

  setSending(false)
  inputRef.current?.focus()
}
