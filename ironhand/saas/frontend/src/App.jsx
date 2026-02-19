import { useState, useEffect } from 'react'
import { Activity, ArrowUpRight, ArrowDownRight, DollarSign, Wallet, Server, ShieldCheck, AlertCircle } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'

// Mock Data
const strategies = [
  { id: 1, name: "BTC-Ladder-Aggressive", status: "Active", pnl: "+$1,240.50", roi: "+12.4%", allocation: "$10,000" },
  { id: 2, name: "ETH-Scalp-Neutral", status: "Active", pnl: "+$450.20", roi: "+4.5%", allocation: "$10,000" },
  { id: 3, name: "SOL-Swing-Defensive", status: "Paused", pnl: "-$120.00", roi: "-1.2%", allocation: "$10,000" },
]

const recentOrders = [
  { id: 101, type: "BUY", asset: "BTC/USD", amount: "0.05", price: "$95,420", time: "10:42 AM", status: "Filled" },
  { id: 102, type: "SELL", asset: "ETH/USD", amount: "1.2", price: "$2,840", time: "10:30 AM", status: "Filled" },
  { id: 103, type: "BUY", asset: "SOL/USD", amount: "15", price: "$142.50", time: "09:15 AM", status: "Pending" },
]

const chartData = [
  { time: '09:00', value: 10000 },
  { time: '10:00', value: 10200 },
  { time: '11:00', value: 10150 },
  { time: '12:00', value: 10400 },
  { time: '13:00', value: 10350 },
  { time: '14:00', value: 10600 },
  { time: '15:00', value: 10800 },
]

function App() {
  const [systemStatus, setSystemStatus] = useState("Checking...")
  
  useEffect(() => {
    // Check backend health
    fetch('http://localhost:8001/health')
      .then(res => res.ok ? setSystemStatus("Online") : setSystemStatus("Error"))
      .catch(() => setSystemStatus("Offline"))
  }, [])

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6 font-mono">
      {/* Header */}
      <header className="flex justify-between items-center mb-8 border-b border-gray-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="bg-blue-600 p-2 rounded-lg">
            <Activity className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">IronHand SaaS</h1>
            <p className="text-xs text-gray-400">Mission Control Dashboard</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${
            systemStatus === "Online" ? "bg-green-900/30 text-green-400 border border-green-800" : 
            "bg-red-900/30 text-red-400 border border-red-800"
          }`}>
            <Server className="w-4 h-4" />
            <span>System: {systemStatus}</span>
          </div>
          <div className="w-8 h-8 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center">
            <span className="text-xs font-bold">RN</span>
          </div>
        </div>
      </header>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <Card title="Total Balance" value="$32,450.00" change="+2.4%" icon={<Wallet className="text-blue-400" />} />
        <Card title="Daily P&L" value="+$450.20" change="+1.2%" icon={<DollarSign className="text-green-400" />} />
        <Card title="Active Strategies" value="2" sub="1 Paused" icon={<ShieldCheck className="text-purple-400" />} />
        <Card title="Open Orders" value="3" sub="Working" icon={<Activity className="text-orange-400" />} />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Main Chart */}
        <div className="lg:col-span-2 bg-gray-900/50 border border-gray-800 rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-500" /> Performance History
          </h3>
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" stroke="#4b5563" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#4b5563" fontSize={12} tickLine={false} axisLine={false} domain={['auto', 'auto']} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: '8px' }}
                  itemStyle={{ color: '#e5e7eb' }}
                />
                <Area type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorValue)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Strategies List */}
        <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-purple-500" /> Active Strategies
          </h3>
          <div className="space-y-4">
            {strategies.map(s => (
              <div key={s.id} className="p-3 bg-gray-800/50 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors">
                <div className="flex justify-between items-start mb-2">
                  <span className="font-bold text-sm">{s.name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    s.status === "Active" ? "bg-green-900/50 text-green-400" : "bg-yellow-900/50 text-yellow-400"
                  }`}>{s.status}</span>
                </div>
                <div className="flex justify-between text-sm text-gray-400">
                  <span>P&L: <span className="text-green-400">{s.pnl}</span></span>
                  <span>{s.roi}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Orders */}
        <div className="lg:col-span-3 bg-gray-900/50 border border-gray-800 rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Activity className="w-4 h-4 text-orange-500" /> Recent Orders
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-gray-400 uppercase bg-gray-800/50">
                <tr>
                  <th className="px-4 py-3 rounded-l-lg">Time</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Asset</th>
                  <th className="px-4 py-3">Price</th>
                  <th className="px-4 py-3">Amount</th>
                  <th className="px-4 py-3 rounded-r-lg">Status</th>
                </tr>
              </thead>
              <tbody>
                {recentOrders.map(order => (
                  <tr key={order.id} className="border-b border-gray-800 hover:bg-gray-800/30">
                    <td className="px-4 py-3 font-mono text-gray-400">{order.time}</td>
                    <td className={`px-4 py-3 font-bold ${order.type === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
                      {order.type}
                    </td>
                    <td className="px-4 py-3">{order.asset}</td>
                    <td className="px-4 py-3">{order.price}</td>
                    <td className="px-4 py-3">{order.amount}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-1 bg-gray-800 rounded text-xs">{order.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  )
}

function Card({ title, value, change, sub, icon }) {
  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-5 flex flex-col justify-between">
      <div className="flex justify-between items-start mb-2">
        <span className="text-gray-400 text-sm font-medium">{title}</span>
        <div className="p-2 bg-gray-800 rounded-lg">{icon}</div>
      </div>
      <div>
        <div className="text-2xl font-bold text-white mb-1">{value}</div>
        {change && (
          <div className="flex items-center text-sm text-green-400">
            <ArrowUpRight className="w-4 h-4 mr-1" />
            {change}
          </div>
        )}
        {sub && <div className="text-sm text-gray-500">{sub}</div>}
      </div>
    </div>
  )
}

export default App
