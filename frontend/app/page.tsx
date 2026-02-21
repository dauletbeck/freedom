"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import {
  Ticket,
  Users,
  TrendingUp,
  AlertCircle,
  RotateCcw,
  ArrowUpDown,
  X,
  ChevronRight,
} from "lucide-react";
import StatsCard from "@/components/StatsCard";
import PipelineButton from "@/components/PipelineButton";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#f97316"];

const SENTIMENT_COLORS: Record<string, string> = {
  Позитивный: "#10b981",
  Нейтральный: "#6b7280",
  Негативный: "#ef4444",
};

type SortMode = "value_desc" | "value_asc" | "name_asc";
type ManagerSortKey = "load" | "name" | "office" | "prior_load" | "assigned_count";
type SortDir = "asc" | "desc";

interface TicketRow {
  id: number;
  guid?: string;
  segment?: string;
  analysis?: {
    ticket_type?: string;
    sentiment?: string;
    language?: string;
    priority_score?: number | null;
  };
  assignment?: {
    assigned_office?: string;
  };
}

interface ManagerRow {
  id: number;
  name?: string;
  office?: string;
  position?: string;
  skills?: string[];
  load?: number;
  assigned_count?: number;
  prior_load?: number;
}

interface StatsResponse {
  total_tickets: number;
  manager_loads: ManagerRow[];
}

const SORT_LABELS: Record<SortMode, string> = {
  value_desc: "По значению ↓",
  value_asc: "По значению ↑",
  name_asc: "По названию A→Я",
};

const MANAGER_SORT_LABELS: Record<ManagerSortKey, string> = {
  load: "Общая нагрузка",
  assigned_count: "Назначено сейчас",
  prior_load: "Базовая нагрузка",
  name: "Имя",
  office: "Офис",
};

function countBy(
  items: TicketRow[],
  keyGetter: (ticket: TicketRow) => string | undefined,
): Record<string, number> {
  const result: Record<string, number> = {};
  for (const item of items) {
    const key = keyGetter(item) || "N/A";
    result[key] = (result[key] || 0) + 1;
  }
  return result;
}

function toChartData(obj: Record<string, number> = {}, sort: SortMode = "value_desc") {
  const data = Object.entries(obj).map(([name, value]) => ({ name, value }));
  if (sort === "value_desc") data.sort((a, b) => b.value - a.value);
  if (sort === "value_asc") data.sort((a, b) => a.value - b.value);
  if (sort === "name_asc") data.sort((a, b) => a.name.localeCompare(b.name, "ru"));
  return data;
}

function managerSortValue(manager: ManagerRow, key: ManagerSortKey): string | number {
  if (key === "load") return manager.load || 0;
  if (key === "assigned_count") return manager.assigned_count || 0;
  if (key === "prior_load") return manager.prior_load || 0;
  if (key === "name") return manager.name || "";
  return manager.office || "";
}

export default function Dashboard() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [tickets, setTickets] = useState<TicketRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedOffice, setSelectedOffice] = useState<string | null>(null);
  const [selectedSentiment, setSelectedSentiment] = useState<string | null>(null);
  const [selectedSegment, setSelectedSegment] = useState<string | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState<string | null>(null);

  const [typeSort, setTypeSort] = useState<SortMode>("value_desc");
  const [officeSort, setOfficeSort] = useState<SortMode>("value_desc");
  const [managerSortKey, setManagerSortKey] = useState<ManagerSortKey>("load");
  const [managerSortDir, setManagerSortDir] = useState<SortDir>("desc");

  const [drawerManager, setDrawerManager] = useState<ManagerRow | null>(null);
  const [drawerTickets, setDrawerTickets] = useState<TicketRow[]>([]);
  const [drawerLoading, setDrawerLoading] = useState(false);

  const fetchDashboardData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [statsRes, ticketsRes] = await Promise.all([
        fetch(`${API}/api/stats`),
        fetch(`${API}/api/tickets?limit=5000`),
      ]);

      if (!statsRes.ok || !ticketsRes.ok) {
        throw new Error("Не удалось загрузить данные дашборда.");
      }

      const statsData = (await statsRes.json()) as StatsResponse;
      const ticketsData = (await ticketsRes.json()) as TicketRow[];

      setStats(statsData);
      setTickets(Array.isArray(ticketsData) ? ticketsData : []);
    } catch (e: any) {
      setError(e?.message || "Ошибка загрузки данных.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  useEffect(() => {
    if (!drawerManager) return;
    setDrawerLoading(true);
    setDrawerTickets([]);
    fetch(`${API}/api/tickets?manager_id=${drawerManager.id}&limit=500`)
      .then((r) => r.json())
      .then((data) => setDrawerTickets(Array.isArray(data) ? data : []))
      .finally(() => setDrawerLoading(false));
  }, [drawerManager]);

  const languageOptions = useMemo(() => {
    return Array.from(
      new Set(
        tickets
          .map((ticket) => ticket.analysis?.language)
          .filter((lang): lang is string => Boolean(lang)),
      ),
    ).sort((a, b) => a.localeCompare(b, "ru"));
  }, [tickets]);

  const filteredTickets = useMemo(() => {
    return tickets.filter((ticket) => {
      if (selectedType && ticket.analysis?.ticket_type !== selectedType) return false;
      if (selectedOffice && ticket.assignment?.assigned_office !== selectedOffice) return false;
      if (selectedSentiment && ticket.analysis?.sentiment !== selectedSentiment) return false;
      if (selectedSegment && ticket.segment !== selectedSegment) return false;
      if (selectedLanguage && ticket.analysis?.language !== selectedLanguage) return false;
      return true;
    });
  }, [tickets, selectedType, selectedOffice, selectedSentiment, selectedSegment, selectedLanguage]);

  const byType = useMemo(
    () => countBy(filteredTickets, (ticket) => ticket.analysis?.ticket_type),
    [filteredTickets],
  );
  const bySentiment = useMemo(
    () => countBy(filteredTickets, (ticket) => ticket.analysis?.sentiment),
    [filteredTickets],
  );
  const byOffice = useMemo(
    () => countBy(filteredTickets, (ticket) => ticket.assignment?.assigned_office),
    [filteredTickets],
  );
  const bySegment = useMemo(
    () => countBy(filteredTickets, (ticket) => ticket.segment),
    [filteredTickets],
  );

  const byTypeData = useMemo(() => toChartData(byType, typeSort), [byType, typeSort]);
  const byOfficeData = useMemo(() => toChartData(byOffice, officeSort).filter((d) => d.name !== "N/A"), [byOffice, officeSort]);
  const bySentimentData = useMemo(() => toChartData(bySentiment, "name_asc"), [bySentiment]);
  const bySegmentData = useMemo(() => toChartData(bySegment, "name_asc"), [bySegment]);

  const avgPriority = useMemo(() => {
    const priorities = filteredTickets
      .map((ticket) => ticket.analysis?.priority_score)
      .filter((value): value is number => typeof value === "number");
    if (!priorities.length) return 0;
    const total = priorities.reduce((sum, value) => sum + value, 0);
    return Number((total / priorities.length).toFixed(2));
  }, [filteredTickets]);

  const managerRows = useMemo(() => {
    const rows = [...(stats?.manager_loads || [])];
    const officeFiltered = selectedOffice ? rows.filter((m) => m.office === selectedOffice) : rows;

    officeFiltered.sort((a, b) => {
      const aValue = managerSortValue(a, managerSortKey);
      const bValue = managerSortValue(b, managerSortKey);

      let compare = 0;
      if (typeof aValue === "number" || typeof bValue === "number") {
        compare = Number(aValue) - Number(bValue);
      } else {
        compare = aValue.localeCompare(bValue, "ru");
      }

      return managerSortDir === "asc" ? compare : -compare;
    });

    return officeFiltered;
  }, [stats?.manager_loads, selectedOffice, managerSortKey, managerSortDir]);

  const hasActiveFilters = Boolean(
    selectedType || selectedOffice || selectedSentiment || selectedSegment || selectedLanguage,
  );

  const resetFilters = () => {
    setSelectedType(null);
    setSelectedOffice(null);
    setSelectedSentiment(null);
    setSelectedSegment(null);
    setSelectedLanguage(null);
  };

  const toggleType = (name?: string) => {
    if (!name) return;
    setSelectedType((current) => (current === name ? null : name));
  };

  const toggleOffice = (name?: string) => {
    if (!name) return;
    setSelectedOffice((current) => (current === name ? null : name));
  };

  const toggleSentiment = (name?: string) => {
    if (!name) return;
    setSelectedSentiment((current) => (current === name ? null : name));
  };

  const toggleSegment = (name?: string) => {
    if (!name) return;
    setSelectedSegment((current) => (current === name ? null : name));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Дашборд</h1>
          <p className="text-sm text-gray-500 mt-0.5">Анализ и распределение обращений</p>
        </div>
        <PipelineButton onComplete={fetchDashboardData} />
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64 text-gray-500">Загрузка...</div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center h-64 gap-3 text-red-400">
          <AlertCircle className="w-12 h-12" />
          <p>{error}</p>
          <button
            onClick={fetchDashboardData}
            className="px-3 py-2 text-sm rounded-lg border border-gray-700 text-gray-300 hover:border-blue-500 hover:text-blue-300 transition-colors"
          >
            Повторить
          </button>
        </div>
      ) : !stats || !tickets.length ? (
        <div className="flex flex-col items-center justify-center h-64 gap-3 text-gray-500">
          <AlertCircle className="w-12 h-12" />
          <p>Нет данных. Запустите пайплайн для обработки обращений.</p>
        </div>
      ) : (
        <>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <h2 className="text-sm font-semibold text-gray-300">Интерактивные фильтры</h2>
              <button
                onClick={resetFilters}
                disabled={!hasActiveFilters}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border border-gray-700 text-gray-300 hover:border-blue-500 hover:text-blue-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Сбросить все
              </button>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              <select
                value={selectedLanguage || ""}
                onChange={(e) => setSelectedLanguage(e.target.value || null)}
                className="bg-gray-950 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-300 focus:outline-none focus:border-blue-500"
              >
                <option value="">Все языки</option>
                {languageOptions.map((language) => (
                  <option key={language} value={language}>
                    {language}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex gap-2 flex-wrap">
              {!hasActiveFilters && <span className="text-xs text-gray-500">Нет активных фильтров</span>}
              {selectedType && (
                <button
                  onClick={() => setSelectedType(null)}
                  className="text-xs px-2 py-1 rounded bg-blue-900/40 text-blue-300 hover:bg-blue-900/60"
                >
                  Тип: {selectedType} ×
                </button>
              )}
              {selectedOffice && (
                <button
                  onClick={() => setSelectedOffice(null)}
                  className="text-xs px-2 py-1 rounded bg-cyan-900/40 text-cyan-300 hover:bg-cyan-900/60"
                >
                  Офис: {selectedOffice} ×
                </button>
              )}
              {selectedSentiment && (
                <button
                  onClick={() => setSelectedSentiment(null)}
                  className="text-xs px-2 py-1 rounded bg-emerald-900/40 text-emerald-300 hover:bg-emerald-900/60"
                >
                  Тональность: {selectedSentiment} ×
                </button>
              )}
              {selectedSegment && (
                <button
                  onClick={() => setSelectedSegment(null)}
                  className="text-xs px-2 py-1 rounded bg-amber-900/40 text-amber-300 hover:bg-amber-900/60"
                >
                  Сегмент: {selectedSegment} ×
                </button>
              )}
              {selectedLanguage && (
                <button
                  onClick={() => setSelectedLanguage(null)}
                  className="text-xs px-2 py-1 rounded bg-violet-900/40 text-violet-300 hover:bg-violet-900/60"
                >
                  Язык: {selectedLanguage} ×
                </button>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatsCard
              title="Всего обращений"
              value={filteredTickets.length}
              sub={`из ${stats.total_tickets}`}
              icon={Ticket}
              color="blue"
            />
            <StatsCard title="Ср. приоритет" value={avgPriority} sub="из 10" icon={TrendingUp} color="orange" />
            <StatsCard
              title="Офисов в выборке"
              value={Object.keys(byOffice).length}
              icon={Users}
              color="green"
            />
            <StatsCard
              title="Менеджеров в таблице"
              value={managerRows.length}
              sub={selectedOffice ? `офис: ${selectedOffice}` : "в текущем списке"}
              icon={Users}
              color="purple"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="mb-3 flex items-center justify-between gap-3 flex-wrap">
                <h2 className="text-sm font-semibold text-gray-300">Типы обращений</h2>
                <select
                  value={typeSort}
                  onChange={(e) => setTypeSort(e.target.value as SortMode)}
                  className="bg-gray-950 border border-gray-700 rounded-lg px-2.5 py-1.5 text-xs text-gray-300 focus:outline-none focus:border-blue-500"
                >
                  {Object.entries(SORT_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <p className="text-xs text-gray-500 mb-3">Клик по столбцу фильтрует все виджеты по типу.</p>
              {byTypeData.length === 0 ? (
                <div className="h-[220px] flex items-center justify-center text-gray-500 text-sm">
                  Нет данных для выбранных фильтров
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={byTypeData} layout="vertical" margin={{ left: 8 }}>
                    <XAxis type="number" tick={{ fill: "#6b7280", fontSize: 11 }} />
                    <YAxis type="category" dataKey="name" width={180} tick={{ fill: "#9ca3af", fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        background: "#1f2937",
                        border: "1px solid #374151",
                        borderRadius: 8,
                      }}
                    />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                      {byTypeData.map((entry, i) => (
                        <Cell
                          key={entry.name}
                          fill={COLORS[i % COLORS.length]}
                          opacity={selectedType && selectedType !== entry.name ? 0.35 : 1}
                          cursor="pointer"
                          onClick={() => toggleType(entry.name)}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-gray-300 mb-3">Тональность</h2>
              <p className="text-xs text-gray-500 mb-3">Клик по сектору фильтрует все виджеты по тональности.</p>
              {bySentimentData.length === 0 ? (
                <div className="h-[220px] flex items-center justify-center text-gray-500 text-sm">
                  Нет данных для выбранных фильтров
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={bySentimentData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                      labelLine={false}
                      onClick={(entry: any) => toggleSentiment(entry?.name)}
                    >
                      {bySentimentData.map((entry, i) => (
                        <Cell
                          key={entry.name}
                          fill={SENTIMENT_COLORS[entry.name] ?? COLORS[i % COLORS.length]}
                          opacity={selectedSentiment && selectedSentiment !== entry.name ? 0.35 : 1}
                          cursor="pointer"
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: "#1f2937",
                        border: "1px solid #374151",
                        borderRadius: 8,
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 lg:col-span-2">
              <div className="mb-3 flex items-center justify-between gap-3 flex-wrap">
                <h2 className="text-sm font-semibold text-gray-300">Обращения по офисам</h2>
                <select
                  value={officeSort}
                  onChange={(e) => setOfficeSort(e.target.value as SortMode)}
                  className="bg-gray-950 border border-gray-700 rounded-lg px-2.5 py-1.5 text-xs text-gray-300 focus:outline-none focus:border-blue-500"
                >
                  {Object.entries(SORT_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <p className="text-xs text-gray-500 mb-3">Клик по столбцу фильтрует все виджеты по офису.</p>
              {byOfficeData.length === 0 ? (
                <div className="h-[200px] flex items-center justify-center text-gray-500 text-sm">
                  Нет данных для выбранных фильтров
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={byOfficeData}>
                    <XAxis
                      dataKey="name"
                      tick={{ fill: "#9ca3af", fontSize: 10 }}
                      angle={-30}
                      textAnchor="end"
                      height={50}
                    />
                    <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        background: "#1f2937",
                        border: "1px solid #374151",
                        borderRadius: 8,
                      }}
                    />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      {byOfficeData.map((entry, i) => (
                        <Cell
                          key={entry.name}
                          fill={COLORS[i % COLORS.length]}
                          opacity={selectedOffice && selectedOffice !== entry.name ? 0.35 : 1}
                          cursor="pointer"
                          onClick={() => toggleOffice(entry.name)}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-gray-300 mb-3">Сегменты</h2>
              <p className="text-xs text-gray-500 mb-3">Клик по сектору фильтрует все виджеты по сегменту.</p>
              {bySegmentData.length === 0 ? (
                <div className="h-[200px] flex items-center justify-center text-gray-500 text-sm">
                  Нет данных для выбранных фильтров
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={bySegmentData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={70}
                      onClick={(entry: any) => toggleSegment(entry?.name)}
                    >
                      {bySegmentData.map((entry, i) => (
                        <Cell
                          key={entry.name}
                          fill={COLORS[i % COLORS.length]}
                          opacity={selectedSegment && selectedSegment !== entry.name ? 0.35 : 1}
                          cursor="pointer"
                        />
                      ))}
                    </Pie>
                    <Legend formatter={(value) => <span className="text-xs text-gray-400">{value}</span>} />
                    <Tooltip
                      contentStyle={{
                        background: "#1f2937",
                        border: "1px solid #374151",
                        borderRadius: 8,
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <div className="mb-4 flex items-center justify-between gap-3 flex-wrap">
              <h2 className="text-sm font-semibold text-gray-300">Нагрузка менеджеров (топ-20)</h2>
              <div className="flex items-center gap-2 flex-wrap">
                <select
                  value={managerSortKey}
                  onChange={(e) => setManagerSortKey(e.target.value as ManagerSortKey)}
                  className="bg-gray-950 border border-gray-700 rounded-lg px-2.5 py-1.5 text-xs text-gray-300 focus:outline-none focus:border-blue-500"
                >
                  {Object.entries(MANAGER_SORT_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => setManagerSortDir((dir) => (dir === "desc" ? "asc" : "desc"))}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-gray-700 text-xs text-gray-300 hover:border-blue-500 hover:text-blue-300 transition-colors"
                >
                  <ArrowUpDown className="w-3.5 h-3.5" />
                  {managerSortDir === "desc" ? "Убыв." : "Возр."}
                </button>
              </div>
            </div>

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
                  {managerRows.slice(0, 20).map((manager) => (
                    <tr
                      key={manager.id}
                      className="border-b border-gray-800/50 hover:bg-gray-800/30 cursor-pointer"
                      onClick={() => setDrawerManager(manager)}
                    >
                      <td className="py-2 pr-4 text-white">{manager.name}</td>
                      <td className="py-2 pr-4 text-gray-400">{manager.office}</td>
                      <td className="py-2 pr-4 text-gray-400 text-xs">{manager.position}</td>
                      <td className="py-2 pr-4">
                        <div className="flex gap-1 flex-wrap">
                          {(manager.skills || []).map((skill) => (
                            <span
                              key={skill}
                              className="px-1.5 py-0.5 rounded text-xs bg-blue-900/40 text-blue-300"
                            >
                              {skill}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-2">
                        <div className="flex items-center gap-2">
                          <div className="w-20 bg-gray-800 rounded-full h-1.5 overflow-hidden flex">
                            <div
                              className="bg-gray-600 h-1.5 shrink-0"
                              style={{
                                width: `${Math.min(
                                  100,
                                  ((manager.prior_load || 0) / Math.max(manager.load || 0, 10)) * 100,
                                )}%`,
                              }}
                              title={`До пайплайна: ${manager.prior_load || 0}`}
                            />
                            <div
                              className="bg-blue-500 h-1.5 shrink-0"
                              style={{
                                width: `${Math.min(
                                  100,
                                  ((manager.assigned_count || 0) / Math.max(manager.load || 0, 10)) * 100,
                                )}%`,
                              }}
                              title={`Назначено: ${manager.assigned_count || 0}`}
                            />
                          </div>
                          <span
                            className="text-gray-300"
                            title={`До: ${manager.prior_load || 0} + Назначено: ${manager.assigned_count || 0}`}
                          >
                            {manager.load || 0}
                            {(manager.assigned_count || 0) > 0 && (
                              <span className="text-gray-500 text-xs"> (+{manager.assigned_count})</span>
                            )}
                          </span>
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

      {/* Manager drawer */}
      {drawerManager && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/50 z-40"
            onClick={() => setDrawerManager(null)}
          />
          {/* Panel */}
          <div className="fixed right-0 top-0 h-full w-full max-w-md bg-gray-950 border-l border-gray-800 z-50 flex flex-col shadow-2xl">
            {/* Header */}
            <div className="p-5 border-b border-gray-800 flex items-start justify-between gap-3">
              <div>
                <p className="text-xs text-gray-500 mb-0.5">Менеджер</p>
                <h2 className="text-base font-semibold text-white">{drawerManager.name}</h2>
                <p className="text-xs text-gray-400 mt-0.5">
                  {drawerManager.position} · {drawerManager.office}
                </p>
                <div className="flex gap-1 flex-wrap mt-2">
                  {(drawerManager.skills || []).map((s) => (
                    <span key={s} className="px-1.5 py-0.5 rounded text-xs bg-blue-900/40 text-blue-300">{s}</span>
                  ))}
                </div>
              </div>
              <button
                onClick={() => setDrawerManager(null)}
                className="text-gray-500 hover:text-white transition-colors mt-0.5"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Stats bar */}
            <div className="px-5 py-3 border-b border-gray-800 flex gap-6 text-xs text-gray-400">
              <span>Нагрузка: <span className="text-white font-semibold">{drawerManager.load ?? 0}</span></span>
              <span>Назначено: <span className="text-blue-300 font-semibold">{drawerManager.assigned_count ?? 0}</span></span>
            </div>

            {/* Ticket list */}
            <div className="flex-1 overflow-y-auto">
              {drawerLoading ? (
                <div className="flex items-center justify-center h-32 text-gray-500 text-sm">Загрузка...</div>
              ) : drawerTickets.length === 0 ? (
                <div className="flex items-center justify-center h-32 text-gray-500 text-sm">Нет назначенных обращений</div>
              ) : (
                <ul className="divide-y divide-gray-800/60">
                  {drawerTickets.map((t) => (
                    <li key={t.id}>
                      <Link
                        href={`/tickets/${t.id}`}
                        className="flex items-center justify-between px-5 py-3 hover:bg-gray-800/40 transition-colors group"
                      >
                        <div className="min-w-0">
                          <p className="text-xs font-mono text-gray-300 truncate group-hover:text-white transition-colors">
                            {t.guid ?? `#${t.id}`}
                          </p>
                          <div className="flex items-center gap-2 mt-1 flex-wrap">
                            {t.analysis?.ticket_type && (
                              <span className="text-xs text-gray-500">{t.analysis.ticket_type}</span>
                            )}
                            {t.analysis?.sentiment && (
                              <span className={`text-xs ${
                                t.analysis.sentiment === "Негативный" ? "text-red-400" :
                                t.analysis.sentiment === "Позитивный" ? "text-green-400" :
                                "text-gray-500"
                              }`}>{t.analysis.sentiment}</span>
                            )}
                            {t.segment && (
                              <span className={`text-xs px-1.5 py-0.5 rounded ${
                                t.segment === "VIP" ? "bg-amber-900/40 text-amber-300" :
                                t.segment === "Priority" ? "bg-blue-900/40 text-blue-300" :
                                "bg-gray-800 text-gray-500"
                              }`}>{t.segment}</span>
                            )}
                          </div>
                        </div>
                        <ChevronRight className="w-4 h-4 text-gray-600 group-hover:text-gray-400 shrink-0 ml-3" />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
