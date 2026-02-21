"use client";

import { useEffect, useState, useCallback } from "react";
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";
import { Ticket, Users, TrendingUp, AlertCircle } from "lucide-react";
import StatsCard from "@/components/StatsCard";
import PipelineButton from "@/components/PipelineButton";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const COLORS = ["#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#f97316"];

const SENTIMENT_COLORS: Record<string,string> = {
  "Позитивный": "#10b981",
  "Нейтральный": "#6b7280",
  "Негативный": "#ef4444",
};

export default function Dashboard() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/stats`);
      const data = await res.json();
      setStats(data);
    } catch {
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  const toChartData = (obj: Record<string, number> = {}) =>
    Object.entries(obj).map(([name, value]) => ({ name, value }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Дашборд</h1>
          <p className="text-sm text-gray-500 mt-0.5">Анализ и распределение обращений</p>
        </div>
        <PipelineButton onComplete={fetchStats} />
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64 text-gray-500">Загрузка...</div>
      ) : !stats?.total_tickets ? (
        <div className="flex flex-col items-center justify-center h-64 gap-3 text-gray-500">
          <AlertCircle className="w-12 h-12" />
          <p>Нет данных. Запустите пайплайн для обработки обращений.</p>
        </div>
      ) : (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatsCard title="Всего обращений" value={stats.total_tickets} icon={Ticket} color="blue" />
            <StatsCard title="Ср. приоритет" value={stats.avg_priority} sub="из 10" icon={TrendingUp} color="orange" />
            <StatsCard
              title="Офисов задействовано"
              value={Object.keys(stats.by_office || {}).length}
              icon={Users}
              color="green"
            />
            <StatsCard
              title="Менеджеров"
              value={stats.manager_loads?.length ?? 0}
              sub="в системе"
              icon={Users}
              color="purple"
            />
          </div>

          {/* Charts row 1 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* By Type */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-gray-300 mb-4">Типы обращений</h2>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={toChartData(stats.by_type)} layout="vertical" margin={{ left: 8 }}>
                  <XAxis type="number" tick={{ fill: "#6b7280", fontSize: 11 }} />
                  <YAxis type="category" dataKey="name" width={160} tick={{ fill: "#9ca3af", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8 }} />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                    {toChartData(stats.by_type).map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* By Sentiment */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-gray-300 mb-4">Тональность</h2>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={toChartData(stats.by_sentiment)}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    labelLine={false}
                  >
                    {toChartData(stats.by_sentiment).map((entry, i) => (
                      <Cell key={i} fill={SENTIMENT_COLORS[entry.name] ?? COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Charts row 2 */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* By Office */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 lg:col-span-2">
              <h2 className="text-sm font-semibold text-gray-300 mb-4">Обращения по офисам</h2>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={toChartData(stats.by_office)}>
                  <XAxis dataKey="name" tick={{ fill: "#9ca3af", fontSize: 10 }} angle={-30} textAnchor="end" height={50} />
                  <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8 }} />
                  <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* By Segment */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-gray-300 mb-4">Сегменты</h2>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={toChartData(stats.by_segment)} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70}>
                    {toChartData(stats.by_segment).map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Legend formatter={(v) => <span className="text-xs text-gray-400">{v}</span>} />
                  <Tooltip contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Manager Loads */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-gray-300 mb-4">Нагрузка менеджеров (топ-20)</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-left border-b border-gray-800">
                    <th className="pb-2 pr-4">Менеджер</th>
                    <th className="pb-2 pr-4">Офис</th>
                    <th className="pb-2 pr-4">Должность</th>
                    <th className="pb-2 pr-4">Навыки</th>
                    <th className="pb-2">Нагрузка</th>
                  </tr>
                </thead>
                <tbody>
                  {(stats.manager_loads || []).slice(0, 20).map((m: any) => (
                    <tr key={m.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                      <td className="py-2 pr-4 text-white">{m.name}</td>
                      <td className="py-2 pr-4 text-gray-400">{m.office}</td>
                      <td className="py-2 pr-4 text-gray-400 text-xs">{m.position}</td>
                      <td className="py-2 pr-4">
                        <div className="flex gap-1 flex-wrap">
                          {(m.skills || []).map((s: string) => (
                            <span key={s} className="px-1.5 py-0.5 rounded text-xs bg-blue-900/40 text-blue-300">{s}</span>
                          ))}
                        </div>
                      </td>
                      <td className="py-2">
                        <div className="flex items-center gap-2">
                          <div className="w-20 bg-gray-800 rounded-full h-1.5">
                            <div
                              className="bg-blue-500 h-1.5 rounded-full"
                              style={{ width: `${Math.min(100, (m.load / 10) * 100)}%` }}
                            />
                          </div>
                          <span className="text-gray-300">{m.load}</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
