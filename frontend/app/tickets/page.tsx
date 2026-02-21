"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Search, Filter } from "lucide-react";
import clsx from "clsx";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SENTIMENT_COLOR: Record<string, string> = {
  Позитивный: "text-green-400",
  Нейтральный: "text-gray-400",
  Негативный: "text-red-400",
};

const TYPE_COLOR: Record<string, string> = {
  "Жалоба": "bg-red-900/40 text-red-300",
  "Смена данных": "bg-yellow-900/40 text-yellow-300",
  "Консультация": "bg-blue-900/40 text-blue-300",
  "Претензия": "bg-orange-900/40 text-orange-300",
  "Неработоспособность приложения": "bg-purple-900/40 text-purple-300",
  "Мошеннические действия": "bg-rose-900/40 text-rose-300",
  "Спам": "bg-gray-800 text-gray-500",
};

const SEGMENTS = ["", "VIP", "Priority", "Mass"];
const LANGUAGES = ["", "RU", "KZ", "ENG"];

export default function TicketsPage() {
  const [tickets, setTickets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [segment, setSegment] = useState("");
  const [language, setLanguage] = useState("");
  const [search, setSearch] = useState("");

  const fetchTickets = async () => {
    setLoading(true);
    const params = new URLSearchParams({ limit: "100" });
    if (segment) params.set("segment", segment);
    if (language) params.set("language", language);
    const res = await fetch(`${API}/api/tickets?${params}`);
    const data = await res.json();
    setTickets(data);
    setLoading(false);
  };

  useEffect(() => { fetchTickets(); }, [segment, language]);

  const filtered = tickets.filter((t) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      t.guid?.toLowerCase().includes(q) ||
      t.city?.toLowerCase().includes(q) ||
      t.description?.toLowerCase().includes(q) ||
      t.assignment?.manager?.full_name?.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-white">Обращения</h1>
        <p className="text-sm text-gray-500 mt-0.5">{filtered.length} обращений</p>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            className="bg-gray-900 border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-gray-500 w-64 focus:outline-none focus:border-blue-500"
            placeholder="Поиск по GUID, городу..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300 focus:outline-none focus:border-blue-500"
          value={segment}
          onChange={(e) => setSegment(e.target.value)}
        >
          <option value="">Все сегменты</option>
          {SEGMENTS.filter(Boolean).map((s) => <option key={s}>{s}</option>)}
        </select>
        <select
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300 focus:outline-none focus:border-blue-500"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
        >
          <option value="">Все языки</option>
          {LANGUAGES.filter(Boolean).map((l) => <option key={l}>{l}</option>)}
        </select>
      </div>

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-left border-b border-gray-800 bg-gray-900/80">
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">GUID</th>
                <th className="px-4 py-3">Тип</th>
                <th className="px-4 py-3">Сегмент</th>
                <th className="px-4 py-3">Язык</th>
                <th className="px-4 py-3">Приоритет</th>
                <th className="px-4 py-3">Тональность</th>
                <th className="px-4 py-3">Город</th>
                <th className="px-4 py-3">Офис</th>
                <th className="px-4 py-3">Менеджер</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={10} className="px-4 py-8 text-center text-gray-500">Загрузка...</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={10} className="px-4 py-8 text-center text-gray-500">Нет данных</td></tr>
              ) : (
                filtered.map((t, i) => (
                  <tr key={t.id} className="border-b border-gray-800/60 hover:bg-gray-800/30 transition-colors">
                    <td className="px-4 py-3 text-gray-600">{i + 1}</td>
                    <td className="px-4 py-3">
                      <Link href={`/tickets/${t.id}`} className="text-blue-400 hover:text-blue-300 font-mono text-xs">
                        {t.guid?.slice(0, 8)}...
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      {t.analysis?.ticket_type ? (
                        <span className={clsx("px-2 py-1 rounded text-xs font-medium", TYPE_COLOR[t.analysis.ticket_type] ?? "bg-gray-800 text-gray-400")}>
                          {t.analysis.ticket_type}
                        </span>
                      ) : <span className="text-gray-600">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      <span className={clsx("px-2 py-1 rounded text-xs", {
                        "bg-amber-900/40 text-amber-300": t.segment === "VIP",
                        "bg-blue-900/40 text-blue-300": t.segment === "Priority",
                        "bg-gray-800 text-gray-400": t.segment === "Mass",
                      })}>
                        {t.segment}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400">{t.analysis?.language ?? "—"}</td>
                    <td className="px-4 py-3">
                      {t.analysis?.priority_score ? (
                        <span className={clsx("font-bold", {
                          "text-red-400": t.analysis.priority_score >= 8,
                          "text-orange-400": t.analysis.priority_score >= 5,
                          "text-green-400": t.analysis.priority_score < 5,
                        })}>
                          {t.analysis.priority_score}
                        </span>
                      ) : "—"}
                    </td>
                    <td className={clsx("px-4 py-3", SENTIMENT_COLOR[t.analysis?.sentiment] ?? "text-gray-500")}>
                      {t.analysis?.sentiment ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-gray-400">{t.city ?? "—"}</td>
                    <td className="px-4 py-3 text-gray-400">{t.assignment?.assigned_office ?? "—"}</td>
                    <td className="px-4 py-3 text-gray-300">{t.assignment?.manager?.full_name ?? "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
