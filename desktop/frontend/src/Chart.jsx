import { useEffect, useRef } from 'react'
import { createChart, CrosshairMode } from 'lightweight-charts'

const API_DEFAULT = import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://127.0.0.1:3141' : '')

export default function Chart({ ticker, signal, height = 360, apiUrl }) {
  const API = apiUrl || API_DEFAULT
  const containerRef = useRef(null)
  const chartRef = useRef(null)

  useEffect(() => {
    if (!ticker || !containerRef.current) return

    // Clean up old chart
    if (chartRef.current) {
      chartRef.current.remove()
      chartRef.current = null
    }

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { color: 'transparent' },
        textColor: '#4a4a60',
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(30, 30, 42, 0.5)' },
        horzLines: { color: 'rgba(30, 30, 42, 0.5)' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: 'rgba(0, 229, 160, 0.3)', width: 1, style: 2 },
        horzLine: { color: 'rgba(0, 229, 160, 0.3)', width: 1, style: 2 },
      },
      rightPriceScale: {
        borderColor: '#1e1e2a',
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
      timeScale: {
        borderColor: '#1e1e2a',
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: true,
      handleScale: true,
    })
    chartRef.current = chart

    // Candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#00e5a0',
      downColor: '#ff3b5c',
      borderUpColor: '#00e5a0',
      borderDownColor: '#ff3b5c',
      wickUpColor: '#00e5a0',
      wickDownColor: '#ff3b5c',
    })

    // Volume series
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
      scaleMargins: { top: 0.8, bottom: 0 },
    })

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    })

    // Fetch data
    fetch(`${API}/api/chart/${ticker}?period=6mo`)
      .then(r => r.json())
      .then(data => {
        if (!data.ok) return

        const { dates, open, high, low, close, volume } = data.data

        // Format for lightweight-charts
        const candles = dates.map((d, i) => ({
          time: d.includes(' ') ? Math.floor(new Date(d).getTime() / 1000) : d,
          open: open[i],
          high: high[i],
          low: low[i],
          close: close[i],
        }))

        const vols = dates.map((d, i) => ({
          time: d.includes(' ') ? Math.floor(new Date(d).getTime() / 1000) : d,
          value: volume[i],
          color: close[i] >= open[i] ? 'rgba(0, 229, 160, 0.25)' : 'rgba(255, 59, 92, 0.25)',
        }))

        candleSeries.setData(candles)
        volumeSeries.setData(vols)

        // Add signal lines if present
        if (signal?.trade) {
          const tr = signal.trade
          const action = signal.action || ''

          if (action.includes('BUY') || action.includes('SELL')) {
            // Entry line
            if (tr.entry) {
              candleSeries.createPriceLine({
                price: tr.entry,
                color: '#3388ff',
                lineWidth: 1,
                lineStyle: 2, // dashed
                axisLabelVisible: true,
                title: `Entry ${tr.entry}`,
              })
            }

            // Stop loss
            if (tr.stop_loss) {
              candleSeries.createPriceLine({
                price: tr.stop_loss,
                color: '#ff3b5c',
                lineWidth: 1,
                lineStyle: 2,
                axisLabelVisible: true,
                title: `Stop ${tr.stop_loss}`,
              })
            }

            // Target 1
            if (tr.target_1) {
              candleSeries.createPriceLine({
                price: tr.target_1,
                color: '#00e5a0',
                lineWidth: 1,
                lineStyle: 2,
                axisLabelVisible: true,
                title: `T1 ${tr.target_1}`,
              })
            }

            // Target 2
            if (tr.target_2) {
              candleSeries.createPriceLine({
                price: tr.target_2,
                color: '#00e5a0',
                lineWidth: 1,
                lineStyle: 3, // dotted
                axisLabelVisible: true,
                title: `T2 ${tr.target_2}`,
              })
            }
          }
        }

        // Add SMA lines
        if (close.length >= 20) {
          const sma20 = calcSMA(close, 20)
          const sma20Data = sma20.map((v, i) => ({
            time: candles[i + (close.length - sma20.length)]?.time,
            value: v,
          })).filter(d => d.time && d.value)

          const smaLine = chart.addLineSeries({
            color: '#3388ff',
            lineWidth: 1,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          })
          smaLine.setData(sma20Data)
        }

        if (close.length >= 50) {
          const sma50 = calcSMA(close, 50)
          const sma50Data = sma50.map((v, i) => ({
            time: candles[i + (close.length - sma50.length)]?.time,
            value: v,
          })).filter(d => d.time && d.value)

          const sma50Line = chart.addLineSeries({
            color: '#ffb020',
            lineWidth: 1,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          })
          sma50Line.setData(sma50Data)
        }

        chart.timeScale().fitContent()
      })
      .catch(() => {})

    // Resize handler
    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      if (chartRef.current) {
        chartRef.current.remove()
        chartRef.current = null
      }
    }
  }, [ticker, signal, height])

  return (
    <div className="chart-container">
      <div className="chart-header">
        <span className="chart-ticker">{ticker}</span>
        <span className="chart-period">6M · Daily</span>
      </div>
      <div ref={containerRef} className="chart-canvas" />
    </div>
  )
}

// Simple Moving Average calc
function calcSMA(data, period) {
  const result = []
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0
    for (let j = 0; j < period; j++) {
      sum += data[i - j]
    }
    result.push(Math.round((sum / period) * 100) / 100)
  }
  return result
}
