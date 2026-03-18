import { useState, useEffect } from 'react'
import axios from 'axios'
import Plot from 'react-plotly.js'
import { Activity, Battery, DollarSign, Zap, Play, Settings, Database, BarChart3, TrendingUp, RefreshCw } from 'lucide-react'
import './App.css'

const API = 'http://127.0.0.1:8000'

function App() {
  const [config, setConfig] = useState(null)
  const [dataSummary, setDataSummary] = useState(null)
  const [simulationData, setSimulationData] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [baseline, setBaseline] = useState(null)
  const [loading, setLoading] = useState(false)
  const [history, setHistory] = useState([])
  const [error, setError] = useState(null)
  const [steps, setSteps] = useState(168)

  // Fetch config, data summary, and history on mount
  useEffect(() => {
    fetchConfig()
    fetchDataSummary()
    fetchHistory()
  }, [])

  const fetchConfig = async () => {
    try {
      const res = await axios.get(`${API}/api/config`)
      setConfig(res.data)
    } catch (err) {
      console.error("Error fetching config:", err)
    }
  }

  const fetchDataSummary = async () => {
    try {
      const res = await axios.get(`${API}/api/data/summary`)
      setDataSummary(res.data)
    } catch (err) {
      console.error("Error fetching data summary:", err)
    }
  }

  const fetchHistory = async () => {
    try {
      const res = await axios.get(`${API}/api/simulation/history`)
      setHistory(res.data)
    } catch (err) {
      console.error("Error fetching history:", err)
    }
  }

  const runSimulation = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await axios.get(`${API}/api/simulation/run?steps=${steps}`)
      setSimulationData(res.data)
      // Fetch metrics and baseline for this run
      const [metricsRes, baselineRes] = await Promise.all([
        axios.get(`${API}/api/simulation/${res.data.id}/metrics`),
        axios.get(`${API}/api/simulation/${res.data.id}/baseline`),
      ])
      setMetrics(metricsRes.data)
      setBaseline(baselineRes.data)
      fetchHistory()
    } catch (err) {
      console.error("Error running simulation:", err)
      setError("Simulation failed. Please try again.")
    }
    setLoading(false)
  }

  const loadRun = async (runId) => {
    setLoading(true)
    setError(null)
    try {
      const [simRes, metricsRes, baselineRes] = await Promise.all([
        axios.get(`${API}/api/simulation/${runId}`),
        axios.get(`${API}/api/simulation/${runId}/metrics`),
        axios.get(`${API}/api/simulation/${runId}/baseline`),
      ])
      setSimulationData(simRes.data)
      setMetrics(metricsRes.data)
      setBaseline(baselineRes.data)
    } catch (err) {
      console.error("Error loading run:", err)
      setError("Failed to load simulation run.")
    }
    setLoading(false)
  }

  // Helper: format INR
  const inr = (v) => '₹' + Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 })
  const pct = (v) => (v * 100).toFixed(1) + '%'

  return (
    <div className="dashboard-container">
      {/* ── Header ── */}
      <header className="header">
        <div className="logo-section">
          <Zap className="logo-icon" size={26} />
          <h1>EMSJB Energy Dashboard</h1>
        </div>
        <div className="header-right">
          <div className="status-badge">
            <span className="status-dot"></span>
            System Online
          </div>
        </div>
      </header>

      {/* ── Main ── */}
      <main className="main-content">

        {/* Controls */}
        <div className="controls-section">
          <select className="step-select" value={steps} onChange={e => setSteps(Number(e.target.value))}>
            <option value={24}>1 Day (24h)</option>
            <option value={168}>1 Week (168h)</option>
            <option value={336}>2 Weeks (336h)</option>
            <option value={720}>1 Month (720h)</option>
          </select>
          <button className="btn-primary" onClick={runSimulation} disabled={loading}>
            {loading ? <><RefreshCw size={16} className="spinner-inline" /> Running...</> : <><Play size={16} /> Run Simulation</>}
          </button>
        </div>

        {error && <div className="error-toast">⚠ {error}</div>}

        {/* ── System Overview ── */}
        <div className="section-title">System Overview</div>
        <div className="info-grid">
          {/* Config Card */}
          <div className="info-card">
            <div className="info-card-header">
              <div className="info-card-icon blue"><Settings size={18} /></div>
              <h2>Battery Configuration</h2>
            </div>
            {config ? (
              <div className="info-grid-inner">
                <div className="info-item"><span className="label">Power Rating</span><span className="value">{config.battery_power_kw.toLocaleString()} kW</span></div>
                <div className="info-item"><span className="label">Energy Capacity</span><span className="value">{config.battery_energy_kwh.toLocaleString()} kWh</span></div>
                <div className="info-item"><span className="label">Round-trip Eff.</span><span className="value">{(config.round_trip_efficiency * 100).toFixed(0)}%</span></div>
                <div className="info-item"><span className="label">Cycle Life</span><span className="value">{config.cycle_life.toLocaleString()}</span></div>
                <div className="info-item"><span className="label">CAPEX</span><span className="value">{inr(config.capex_inr)}</span></div>
                <div className="info-item"><span className="label">OPEX / Year</span><span className="value">{inr(config.opex_per_year_inr)}</span></div>
                <div className="info-item"><span className="label">Forecast Lag</span><span className="value">{config.forecast_lag_hours}h</span></div>
                <div className="info-item"><span className="label">CVaR α</span><span className="value">{config.cvar_alpha}</span></div>
              </div>
            ) : <p style={{color: 'var(--text-muted)', fontSize: '0.85rem'}}>Loading...</p>}
          </div>

          {/* Dataset Card */}
          <div className="info-card">
            <div className="info-card-header">
              <div className="info-card-icon green"><Database size={18} /></div>
              <h2>Dataset Overview</h2>
            </div>
            {dataSummary ? (
              <div className="info-grid-inner">
                <div className="info-item"><span className="label">Total Hours</span><span className="value">{dataSummary.total_hours.toLocaleString()}</span></div>
                <div className="info-item"><span className="label">Date Range</span><span className="value" style={{fontSize: '0.78rem'}}>{dataSummary.date_start.split(' ')[0]} → {dataSummary.date_end.split(' ')[0]}</span></div>
                <div className="info-item"><span className="label">Mean Price</span><span className="value">₹{dataSummary.price_mean}/kWh</span></div>
                <div className="info-item"><span className="label">Std Dev</span><span className="value">₹{dataSummary.price_std}/kWh</span></div>
                <div className="info-item"><span className="label">Min Price</span><span className="value">₹{dataSummary.price_min}/kWh</span></div>
                <div className="info-item"><span className="label">Max Price</span><span className="value">₹{dataSummary.price_max}/kWh</span></div>
              </div>
            ) : <p style={{color: 'var(--text-muted)', fontSize: '0.85rem'}}>Loading...</p>}
          </div>
        </div>

        {/* ── Loading State ── */}
        {loading && (
          <div className="loading-overlay">
            <div className="spinner"></div>
            <p className="loading-text">Running CVaR optimization for {steps} hours... This may take a minute.</p>
          </div>
        )}

        {/* ── KPI Cards ── */}
        {metrics && !loading && (
          <>
            <div className="section-title">Key Performance Indicators</div>
            <div className="kpi-grid">
              <div className="kpi-card">
                <div className="kpi-icon profit"><DollarSign size={22} /></div>
                <div className="kpi-content">
                  <h3>Total Profit</h3>
                  <p className="kpi-value">{inr(metrics.total_profit)}</p>
                  <p className="kpi-sub">over {steps} hours</p>
                </div>
              </div>
              <div className="kpi-card">
                <div className="kpi-icon daily"><TrendingUp size={22} /></div>
                <div className="kpi-content">
                  <h3>Avg Daily Profit</h3>
                  <p className="kpi-value">{inr(metrics.avg_daily_profit)}</p>
                  <p className="kpi-sub">per day</p>
                </div>
              </div>
              <div className="kpi-card">
                <div className="kpi-icon cycles"><Battery size={22} /></div>
                <div className="kpi-content">
                  <h3>Total Cycles</h3>
                  <p className="kpi-value">{metrics.total_cycles.toFixed(1)}</p>
                  <p className="kpi-sub">{inr(metrics.profit_per_cycle)} per cycle</p>
                </div>
              </div>
              <div className="kpi-card">
                <div className="kpi-icon util"><Activity size={22} /></div>
                <div className="kpi-content">
                  <h3>Utilization</h3>
                  <p className="kpi-value">{pct(metrics.utilization_rate)}</p>
                  <p className="kpi-sub">active hours</p>
                </div>
              </div>
            </div>
          </>
        )}

        {/* ── Charts ── */}
        {simulationData && simulationData.steps.length > 0 && !loading && (
          <>
            <div className="section-title">Simulation Charts</div>
            <div className="charts-grid">
              {/* Price & Battery Operation */}
              <div className="chart-card full-width">
                <h2>Market Price &amp; Battery Operation</h2>
                <Plot
                  data={[
                    {
                      x: simulationData.steps.map(s => s.step_index),
                      y: simulationData.steps.map(s => s.price),
                      type: 'scatter', mode: 'lines',
                      name: 'Price (₹/kWh)',
                      line: { color: '#3b82f6', width: 1.5 }
                    },
                    {
                      x: simulationData.steps.map(s => s.step_index),
                      y: simulationData.steps.map(s => s.soc),
                      type: 'scatter', mode: 'lines',
                      name: 'SOC (kWh)',
                      yaxis: 'y2',
                      line: { color: '#10b981', width: 2, dash: 'dot' }
                    },
                    {
                      x: simulationData.steps.map(s => s.step_index),
                      y: simulationData.steps.map(s => s.battery_power),
                      type: 'bar',
                      name: 'Power (kW)',
                      yaxis: 'y2',
                      marker: {
                        color: simulationData.steps.map(s =>
                          s.battery_power >= 0 ? 'rgba(239,68,68,0.5)' : 'rgba(34,197,94,0.5)'
                        ),
                      },
                    }
                  ]}
                  layout={{
                    autosize: true, height: 420,
                    yaxis: { title: 'Price (₹/kWh)', gridcolor: '#f1f5f9' },
                    yaxis2: { title: 'Power (kW) / SOC (kWh)', overlaying: 'y', side: 'right', gridcolor: '#f1f5f9' },
                    legend: { orientation: 'h', y: 1.12 },
                    margin: { l: 55, r: 55, t: 20, b: 45 },
                    plot_bgcolor: '#fafbfc',
                    paper_bgcolor: 'transparent',
                    font: { family: 'Inter', size: 12 },
                  }}
                  useResizeHandler={true}
                  style={{ width: "100%", height: "100%" }}
                  config={{ displayModeBar: false }}
                />
              </div>

              {/* Cumulative Profit */}
              <div className="chart-card">
                <h2>Cumulative Profit</h2>
                <Plot
                  data={[{
                    x: simulationData.steps.map(s => s.step_index),
                    y: simulationData.steps.reduce((acc, s) => {
                      const last = acc.length > 0 ? acc[acc.length - 1] : 0
                      acc.push(last + s.profit)
                      return acc
                    }, []),
                    type: 'scatter', mode: 'lines',
                    fill: 'tozeroy',
                    name: 'Cumulative Profit',
                    line: { color: '#10b981', width: 2 },
                    fillcolor: 'rgba(16,185,129,0.1)',
                  }]}
                  layout={{
                    autosize: true, height: 300,
                    yaxis: { title: 'Profit (₹)', gridcolor: '#f1f5f9' },
                    xaxis: { title: 'Hour', gridcolor: '#f1f5f9' },
                    margin: { l: 60, r: 20, t: 10, b: 45 },
                    plot_bgcolor: '#fafbfc', paper_bgcolor: 'transparent',
                    font: { family: 'Inter', size: 12 },
                  }}
                  useResizeHandler={true}
                  style={{ width: "100%", height: "100%" }}
                  config={{ displayModeBar: false }}
                />
              </div>

              {/* SOC Distribution */}
              <div className="chart-card">
                <h2>SOC Distribution</h2>
                <Plot
                  data={[{
                    x: simulationData.steps.map(s => s.soc),
                    type: 'histogram',
                    name: 'SOC',
                    marker: { color: '#8b5cf6' },
                    nbinsx: 30,
                  }]}
                  layout={{
                    autosize: true, height: 300,
                    xaxis: { title: 'SOC (kWh)', gridcolor: '#f1f5f9' },
                    yaxis: { title: 'Frequency', gridcolor: '#f1f5f9' },
                    margin: { l: 55, r: 20, t: 10, b: 45 },
                    plot_bgcolor: '#fafbfc', paper_bgcolor: 'transparent',
                    font: { family: 'Inter', size: 12 },
                    bargap: 0.05,
                  }}
                  useResizeHandler={true}
                  style={{ width: "100%", height: "100%" }}
                  config={{ displayModeBar: false }}
                />
              </div>
            </div>
          </>
        )}

        {/* ── Baseline Comparison ── */}
        {baseline && !loading && (
          <>
            <div className="section-title">Strategy Comparison</div>
            <div className="baseline-grid">
              {[
                { data: baseline.optimized, cls: 'optimized' },
                { data: baseline.naive, cls: '' },
                { data: baseline.no_storage, cls: '' },
              ].map(({ data, cls }) => (
                <div className={`baseline-card ${cls}`} key={data.strategy}>
                  <h3>{data.strategy}</h3>
                  <p className={`baseline-profit ${data.total_profit > 0 ? 'positive' : data.total_profit < 0 ? 'negative' : 'zero'}`}>
                    {inr(data.total_profit)}
                  </p>
                  <div className="baseline-stats">
                    <div className="baseline-stat"><span className="label">Cycles</span><span className="value">{data.total_cycles.toFixed(1)}</span></div>
                    <div className="baseline-stat"><span className="label">Sharpe Ratio</span><span className="value">{data.sharpe_ratio.toFixed(3)}</span></div>
                    <div className="baseline-stat"><span className="label">Utilization</span><span className="value">{pct(data.utilization_rate)}</span></div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {/* ── Detailed Metrics ── */}
        {metrics && !loading && (
          <>
            <div className="section-title">Detailed Performance Metrics</div>
            <div className="metrics-card">
              <table className="metrics-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Value</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  <tr><td>Total Profit</td><td>{inr(metrics.total_profit)}</td><td>Sum of all hourly profits from battery arbitrage</td></tr>
                  <tr><td>Avg Daily Profit</td><td>{inr(metrics.avg_daily_profit)}</td><td>Mean profit per calendar day</td></tr>
                  <tr><td>Total Cycles</td><td>{metrics.total_cycles.toFixed(2)}</td><td>Equivalent full charge/discharge cycles consumed</td></tr>
                  <tr><td>Profit per Cycle</td><td>{inr(metrics.profit_per_cycle)}</td><td>Revenue earned per equivalent full cycle</td></tr>
                  <tr><td>Max Drawdown</td><td>{inr(metrics.max_drawdown)}</td><td>Worst peak-to-trough cumulative loss</td></tr>
                  <tr><td>Sharpe Ratio</td><td>{metrics.sharpe_ratio.toFixed(4)}</td><td>Annualised risk-adjusted return (higher is better)</td></tr>
                  <tr><td>Utilization Rate</td><td>{pct(metrics.utilization_rate)}</td><td>Fraction of hours the battery was active</td></tr>
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* ── History ── */}
        <div className="section-title">Simulation History</div>
        {history.length > 0 ? (
          <div className="history-card">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Run #</th>
                  <th>Date & Time</th>
                  <th>Total Profit</th>
                  <th>Steps</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {history.map(run => (
                  <tr key={run.id}>
                    <td>#{run.id}</td>
                    <td>{new Date(run.timestamp).toLocaleString()}</td>
                    <td className={run.total_profit >= 0 ? 'profit-positive' : 'profit-negative'}>
                      {inr(run.total_profit)}
                    </td>
                    <td>{run.steps?.length || '—'}</td>
                    <td><button className="btn-view" onClick={() => loadRun(run.id)}>View</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="history-card">
            <div className="empty-state">
              <BarChart3 size={36} />
              <p>No simulations yet. Run one above to get started!</p>
            </div>
          </div>
        )}

      </main>
    </div>
  )
}

export default App
