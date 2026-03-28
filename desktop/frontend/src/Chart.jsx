import { useEffect, useRef, useState } from 'react'
import { createChart, CrosshairMode } from 'lightweight-charts'

const API_DEFAULT = import.meta.env.VITE_API_URL || (window.location.hostname === 'localhost' ? 'http://127.0.0.1:3141' : 'https://scurrilously-inevasible-kailey.ngrok-free.dev')

export default function Chart({ ticker, signal, height = 360, apiUrl }) {
  const API = apiUrl || API_DEFAULT
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const [priceInfo, setPriceInfo] = useState(null)
  const [period, setPeriod] = useState('1y')

  useEffect(() => {
    if (!ticker || !containerRef.current) return
    if (chartRef.current) { chartRef.current.remove(); chartRef.current = null }

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth, height,
      layout: { background: { color: 'transparent' }, textColor: '#484860', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
      grid: { vertLines: { color: 'rgba(28,28,40,0.4)' }, horzLines: { color: 'rgba(28,28,40,0.4)' } },
      crosshair: { mode: CrosshairMode.Normal,
        vertLine: { color: 'rgba(0,229,160,0.2)', width: 1, style: 2, labelBackgroundColor: '#131319' },
        horzLine: { color: 'rgba(0,229,160,0.2)', width: 1, style: 2, labelBackgroundColor: '#131319' } },
      rightPriceScale: { borderColor: '#1c1c28', scaleMargins: { top: 0.08, bottom: 0.22 } },
      timeScale: { borderColor: '#1c1c28', timeVisible: true, secondsVisible: false },
      handleScroll: true, handleScale: true,
    })
    chartRef.current = chart

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#00e5a0', downColor: '#ff3b5c',
      borderUpColor: '#00e5a0', borderDownColor: '#ff3b5c',
      wickUpColor: '#00c488', wickDownColor: '#cc2244',
    })

    const volumeSeries = chart.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: 'volume' })
    chart.priceScale('volume').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })

    fetch(`${API}/api/chart/${ticker}?period=${period || '1y'}`).then(r => r.json()).then(data => {
      if (!data.ok) return
      const { dates, open, high, low, close, volume } = data.data

      const parseTime = (d) => {
        // Strip time portion, use just the date string YYYY-MM-DD
        const dateOnly = d.split(' ')[0]
        return dateOnly
      }

      const candles = dates.map((d, i) => ({
        time: parseTime(d),
        open: open[i], high: high[i], low: low[i], close: close[i],
      }))
      const vols = dates.map((d, i) => ({
        time: parseTime(d),
        value: volume[i],
        color: close[i] >= open[i] ? 'rgba(0,229,160,0.18)' : 'rgba(255,59,92,0.18)',
      }))

      candleSeries.setData(candles)
      volumeSeries.setData(vols)

      const last = candles[candles.length - 1], prev = candles[candles.length - 2]
      if (last && prev) {
        setPriceInfo({ open: last.open, high: last.high, low: last.low, close: last.close,
          change: last.close - prev.close, changePct: (last.close - prev.close) / prev.close * 100,
          volume: volume[volume.length - 1] })
      }

      // 9 EMA
      if (close.length >= 9) {
        const ema9 = calcEMA(close, 9)
        chart.addLineSeries({ color: '#8866ff', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, title: '9E' })
          .setData(ema9.map((v, i) => ({ time: candles[i + (close.length - ema9.length)]?.time, value: v })).filter(d => d.time && d.value))
      }
      // 20 SMA
      if (close.length >= 20) {
        chart.addLineSeries({ color: '#3388ff', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, title: '20' })
          .setData(calcSMA(close, 20).map((v, i) => ({ time: candles[i + (close.length - calcSMA(close,20).length)]?.time, value: v })).filter(d => d.time && d.value))
      }
      // 50 SMA
      if (close.length >= 50) {
        chart.addLineSeries({ color: '#ffb020', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, title: '50' })
          .setData(calcSMA(close, 50).map((v, i) => ({ time: candles[i + (close.length - calcSMA(close,50).length)]?.time, value: v })).filter(d => d.time && d.value))
      }
      // 200 SMA
      if (close.length >= 200) {
        chart.addLineSeries({ color: '#ff3b5c', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, title: '200' })
          .setData(calcSMA(close, 200).map((v, i) => ({ time: candles[i + (close.length - calcSMA(close,200).length)]?.time, value: v })).filter(d => d.time && d.value))
      }
      // Bollinger Bands
      if (close.length >= 20) {
        const { upper, lower } = calcBollinger(close, 20, 2)
        chart.addLineSeries({ color: 'rgba(72,72,96,0.45)', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
          .setData(upper.map((v, i) => ({ time: candles[i + (close.length - upper.length)]?.time, value: v })).filter(d => d.time && d.value))
        chart.addLineSeries({ color: 'rgba(72,72,96,0.45)', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
          .setData(lower.map((v, i) => ({ time: candles[i + (close.length - lower.length)]?.time, value: v })).filter(d => d.time && d.value))
      }

      // Signal lines
      if (signal?.trade) {
        const tr = signal.trade, action = signal.action || ''
        if (action.includes('BUY') || action.includes('SELL')) {
          if (tr.entry) candleSeries.createPriceLine({ price: tr.entry, color: '#3388ff', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'Entry' })
          if (tr.stop_loss) candleSeries.createPriceLine({ price: tr.stop_loss, color: '#ff3b5c', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'Stop' })
          if (tr.target_1) candleSeries.createPriceLine({ price: tr.target_1, color: '#00e5a0', lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: 'T1' })
          if (tr.target_2) candleSeries.createPriceLine({ price: tr.target_2, color: '#00e5a0', lineWidth: 1, lineStyle: 3, axisLabelVisible: true, title: 'T2' })
        }
      }

      chart.timeScale().fitContent()

      // Crosshair → OHLC update
      chart.subscribeCrosshairMove((param) => {
        if (!param.time || !param.seriesData) {
          if (last && prev) setPriceInfo({ open: last.open, high: last.high, low: last.low, close: last.close,
            change: last.close - prev.close, changePct: (last.close - prev.close) / prev.close * 100, volume: volume[volume.length - 1] })
          return
        }
        const bar = param.seriesData.get(candleSeries)
        if (bar) {
          const idx = candles.findIndex(c => c.time === param.time)
          const p = idx > 0 ? candles[idx - 1] : bar
          const vol = param.seriesData.get(volumeSeries)
          setPriceInfo({ open: bar.open, high: bar.high, low: bar.low, close: bar.close,
            change: bar.close - p.close, changePct: (bar.close - p.close) / p.close * 100, volume: vol?.value || 0 })
        }
      })
    }).catch(() => {})

    const handleResize = () => { if (containerRef.current && chartRef.current) chartRef.current.applyOptions({ width: containerRef.current.clientWidth }) }
    window.addEventListener('resize', handleResize)
    return () => { window.removeEventListener('resize', handleResize); if (chartRef.current) { chartRef.current.remove(); chartRef.current = null } }
  }, [ticker, signal, height, period])

  const fmtVol = (v) => { if (!v) return '0'; if (v >= 1e9) return (v/1e9).toFixed(1)+'B'; if (v >= 1e6) return (v/1e6).toFixed(1)+'M'; if (v >= 1e3) return (v/1e3).toFixed(0)+'K'; return v.toString() }

  return (
    <div className="chart-container">
      <div className="chart-header">
        <span className="chart-ticker">{ticker}</span>
        {signal?.action && (
          <span className={`chart-signal ${signal.action.includes('BUY') ? 'signal-buy' : signal.action.includes('SELL') ? 'signal-sell' : 'signal-hold'}`}>
            {signal.action} · {signal.score}
          </span>
        )}
        <div className="chart-periods">
          {['1mo','3mo','6mo','1y','2y'].map(p => (
            <button key={p} className={'cp-btn' + (period === p ? ' cp-active' : '')} onClick={() => setPeriod(p)}>
              {p.replace('mo','M').replace('y','Y')}
            </button>
          ))}
        </div>
        <div className="chart-legend">
          <span style={{color: '#8866ff'}}>9E</span>
          <span style={{color: '#3388ff'}}>20</span>
          <span style={{color: '#ffb020'}}>50</span>
          <span style={{color: '#ff3b5c'}}>200</span>
          <span style={{color: 'rgba(72,72,96,0.7)'}}>BB</span>
        </div>
      </div>
      {priceInfo && (
        <div className="chart-ohlc">
          <span>O <b>{priceInfo.open?.toFixed(2)}</b></span>
          <span>H <b>{priceInfo.high?.toFixed(2)}</b></span>
          <span>L <b>{priceInfo.low?.toFixed(2)}</b></span>
          <span>C <b style={{color: priceInfo.change >= 0 ? '#00e5a0' : '#ff3b5c'}}>{priceInfo.close?.toFixed(2)}</b></span>
          <span style={{color: priceInfo.change >= 0 ? '#00e5a0' : '#ff3b5c'}}>
            {priceInfo.change >= 0 ? '+' : ''}{priceInfo.change?.toFixed(2)} ({priceInfo.changePct?.toFixed(2)}%)
          </span>
          <span>Vol <b>{fmtVol(priceInfo.volume)}</b></span>
        </div>
      )}
      <div ref={containerRef} className="chart-canvas" />
    </div>
  )
}

function calcSMA(data, period) {
  const r = []; for (let i = period-1; i < data.length; i++) { let s=0; for (let j=0; j<period; j++) s += data[i-j]; r.push(Math.round(s/period*100)/100) }; return r
}
function calcEMA(data, period) {
  const k = 2/(period+1), r = [data[0]]; for (let i=1; i<data.length; i++) r.push(data[i]*k + r[i-1]*(1-k)); return r.slice(period-1).map(v => Math.round(v*100)/100)
}
function calcBollinger(data, period, mult) {
  const upper=[], lower=[]; for (let i=period-1; i<data.length; i++) { let s=0; for (let j=0; j<period; j++) s+=data[i-j]; const m=s/period; let sq=0; for (let j=0; j<period; j++) sq+=Math.pow(data[i-j]-m,2); const std=Math.sqrt(sq/period); upper.push(Math.round((m+mult*std)*100)/100); lower.push(Math.round((m-mult*std)*100)/100) }; return {upper, lower}
}
