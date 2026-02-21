"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";

function LoadBar({ total, assigned, prior }: { total: number; assigned: number; prior: number }) {
  const CAP = Math.max(total, 10);
  const priorPct = Math.min(100, (prior / CAP) * 100);
  const assignedPct = Math.min(100 - priorPct, (assigned / CAP) * 100);
  const barColor = total >= 8 ? "bg-red-500" : total >= 5 ? "bg-orange-500" : "bg-green-500";
  return (
    <div className="flex items-center gap-2">
      <div className="w-24 bg-gray-800 rounded-full h-1.5 overflow-hidden flex">
        <div className="bg-gray-600 h-1.5 shrink-0" style={{ width: `${priorPct}%` }} title={`До пайплайна: ${prior}`} />
        <div className={clsx("h-1.5 shrink-0", barColor)} style={{ width: `${assignedPct}%` }} title={`Назначено: ${assigned}`} />
      </div>
      <span className="text-gray-300 text-xs" title={`До: ${prior} + Назначено: ${assigned}`}>
        {total}
        {assigned > 0 && <span className="text-gray-500"> (+{assigned})</span>}
      </span>
    </div>
  );
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const POSITION_COLOR: Record<string, string> = {
  "Главный специалист": "bg-amber-900/40 text-amber-300",
  "Ведущий специалист": "bg-blue-900/40 text-blue-300",
  "Специалист": "bg-gray-800 text-gray-400",
};

export default function ManagersPage() {
  const [managers, setManagers] = useState<any[]>([]);
  const [offices, setOffices] = useState<string[]>([]);
  const [selectedOffice, setSelectedOffice] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch(`${API}/api/managers`).then((r) => r.json()),
    ]).then(([m]) => {
      setManagers(m);
      const uniqueOffices = Array.from(new Set(m.map((x: any) => x.office).filter(Boolean))) as string[];
      setOffices(uniqueOffices.sort());
      setLoading(false);
    });
  }, []);

  const filtered = selectedOffice
    ? managers.filter((m) => m.office === selectedOffice)
    : managers;

  // Group by office
  const grouped: Record<string, any[]> = {};
  filtered.forEach((m) => {
    const key = m.office || "N/A";
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(m);
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Менеджеры</h1>
          <p className="text-sm text-gray-500 mt-0.5">{filtered.length} сотрудников</p>
        </div>
        <select
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-300 focus:outline-none focus:border-blue-500"
          value={selectedOffice}
          onChange={(e) => setSelectedOffice(e.target.value)}
        >
          <option value="">Все офисы</option>
          {offices.map((o) => <option key={o}>{o}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="text-gray-500">Загрузка...</div>
      ) : (
        Object.entries(grouped).sort().map(([office, mgrs]) => (
          <div key={office} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-800 flex items-center justify-between">
              <h2 className="font-semibold text-white">{office}</h2>
              <span className="text-xs text-gray-500">{mgrs.length} менеджеров</span>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-left border-b border-gray-800/50">
                  <th className="px-5 py-2.5">ФИО</th>
                  <th className="px-5 py-2.5">Должность</th>
                  <th className="px-5 py-2.5">Навыки</th>
                  <th className="px-5 py-2.5">Нагрузка</th>
                </tr>
              </thead>
              <tbody>
                {mgrs.sort((a, b) => b.current_load - a.current_load).map((m) => (
                  <tr key={m.id} className="border-b border-gray-800/30 hover:bg-gray-800/20">
                    <td className="px-5 py-2.5 text-white">{m.full_name}</td>
                    <td className="px-5 py-2.5">
                      <span className={clsx("px-2 py-0.5 rounded text-xs", POSITION_COLOR[m.position] ?? "bg-gray-800 text-gray-400")}>
                        {m.position}
                      </span>
                    </td>
                    <td className="px-5 py-2.5">
                      <div className="flex gap-1 flex-wrap">
                        {(m.skills || []).map((s: string) => (
                          <span key={s} className="px-1.5 py-0.5 rounded text-xs bg-blue-900/30 text-blue-300">{s}</span>
                        ))}
                      </div>
                    </td>
                    <td className="px-5 py-2.5">
                      <LoadBar total={m.current_load} assigned={m.assigned_count} prior={m.prior_load} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))
      )}
    </div>
  );
}
