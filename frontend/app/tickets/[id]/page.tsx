"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, MapPin, User, Brain, Star, Paperclip, AlertTriangle, Lightbulb } from "lucide-react";
import clsx from "clsx";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const PRIORITY_COLOR = (p: number) =>
  p >= 8 ? "text-red-400" : p >= 5 ? "text-orange-400" : "text-green-400";

const SENTIMENT_COLOR: Record<string, string> = {
  Позитивный: "text-green-400 bg-green-900/20",
  Нейтральный: "text-gray-400 bg-gray-800/40",
  Негативный: "text-red-400 bg-red-900/20",
};

function Section({ title, icon: Icon, children }: any) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
      <div className="flex items-center gap-2 text-gray-300 font-semibold text-sm">
        <Icon className="w-4 h-4" />
        {title}
      </div>
      {children}
    </div>
  );
}

function Row({ label, value, className = "" }: { label: string; value: React.ReactNode; className?: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-gray-500 text-sm w-40 shrink-0">{label}</span>
      <span className={clsx("text-sm text-gray-200", className)}>{value ?? "—"}</span>
    </div>
  );
}

export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [ticket, setTicket] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/api/tickets/${id}`)
      .then((r) => r.json())
      .then(setTicket)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="text-gray-500">Загрузка...</div>;
  if (!ticket) return <div className="text-red-400">Обращение не найдено</div>;

  const a = ticket.analysis;
  const m = ticket.assignment?.manager;

  return (
    <div className="space-y-5 max-w-4xl">
      {/* Back */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-2 text-gray-400 hover:text-white text-sm transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> Назад
      </button>

      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-white font-mono">{ticket.guid}</h1>
        <div className="flex items-center gap-3 mt-2">
          <span className={clsx("px-2 py-0.5 rounded text-xs font-medium", {
            "bg-amber-900/40 text-amber-300": ticket.segment === "VIP",
            "bg-blue-900/40 text-blue-300": ticket.segment === "Priority",
            "bg-gray-800 text-gray-400": ticket.segment === "Mass",
          })}>
            {ticket.segment}
          </span>
          {a?.ticket_type && (
            <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-800 text-gray-300">
              {a.ticket_type}
            </span>
          )}
          {a?.language && (
            <span className="px-2 py-0.5 rounded text-xs bg-blue-900/30 text-blue-300">{a.language}</span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Client info */}
        <Section title="Клиент" icon={User}>
          <Row label="Пол" value={ticket.gender} />
          <Row label="Дата рождения" value={ticket.birth_date} />
          <Row label="Страна" value={ticket.country} />
          <Row label="Регион" value={ticket.region} />
          <Row label="Город" value={ticket.city} />
          <Row label="Адрес" value={[ticket.street, ticket.house].filter(Boolean).join(", ") || null} />
          {ticket.attachment && (
            <Row label="Вложение" value={<span className="text-blue-400">{ticket.attachment}</span>} />
          )}
        </Section>

        {/* AI Analysis */}
        <Section title="AI Анализ" icon={Brain}>
          {!a ? (
            <p className="text-gray-500 text-sm">Анализ не выполнен</p>
          ) : (
            <>
              <Row label="Тип" value={a.ticket_type} />
              <Row label="Тональность" value={
                <span className={clsx("px-2 py-0.5 rounded text-xs", SENTIMENT_COLOR[a.sentiment])}>
                  {a.sentiment}
                </span>
              } />
              <Row label="Приоритет" value={
                <span className={clsx("font-bold text-lg", PRIORITY_COLOR(a.priority_score))}>
                  {a.priority_score}/10
                </span>
              } />
              <Row label="Язык" value={a.language} />
              {a.client_lat && (
                <Row label="Координаты" value={`${a.client_lat?.toFixed(4)}, ${a.client_lon?.toFixed(4)}`} />
              )}
              <div className="pt-2 border-t border-gray-800">
                <p className="text-xs text-gray-500 mb-1">Суть обращения</p>
                <p className="text-sm text-gray-200 leading-relaxed">{a.summary}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Рекомендация</p>
                <p className="text-sm text-blue-300 leading-relaxed">{a.recommendation}</p>
              </div>
              {a.attachment_description && (
                <div className={clsx("pt-2 border-t border-gray-800 rounded-lg p-3",
                  a.attachment_description.startsWith("⚠️")
                    ? "bg-yellow-900/20 border border-yellow-700/40"
                    : "bg-gray-800/40"
                )}>
                  <div className="flex items-center gap-1.5 mb-1">
                    {a.attachment_description.startsWith("⚠️")
                      ? <AlertTriangle className="w-3.5 h-3.5 text-yellow-400" />
                      : <Paperclip className="w-3.5 h-3.5 text-gray-400" />
                    }
                    <p className="text-xs text-gray-500">Вложение</p>
                  </div>
                  <p className={clsx("text-sm leading-relaxed whitespace-pre-wrap",
                    a.attachment_description.startsWith("⚠️") ? "text-yellow-300" : "text-gray-300"
                  )}>
                    {a.attachment_description}
                  </p>
                </div>
              )}
            </>
          )}
        </Section>
      </div>

      {/* Description */}
      <Section title="Текст обращения" icon={Star}>
        <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
          {ticket.description || <span className="text-gray-600">Описание отсутствует</span>}
        </p>
      </Section>

      {/* Assignment */}
      <Section title="Назначение" icon={MapPin}>
        {!ticket.assignment ? (
          <p className="text-gray-500 text-sm">Назначение не выполнено</p>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-gray-500 mb-2">Офис</p>
                <p className="text-white font-semibold">{ticket.assignment.assigned_office}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-2">Round Robin индекс</p>
                <p className="text-gray-300">{ticket.assignment.round_robin_index}</p>
              </div>
              {m && (
                <>
                  <div>
                    <p className="text-xs text-gray-500 mb-2">Менеджер</p>
                    <p className="text-white font-semibold">{m.full_name}</p>
                    <p className="text-xs text-gray-500">{m.position}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 mb-2">Навыки менеджера</p>
                    <div className="flex gap-1 flex-wrap">
                      {(m.skills || []).map((s: string) => (
                        <span key={s} className="px-2 py-0.5 rounded text-xs bg-blue-900/40 text-blue-300">{s}</span>
                      ))}
                    </div>
                    <p className="text-xs text-gray-500 mt-1">Нагрузка: {m.current_load}</p>
                  </div>
                </>
              )}
            </div>
            {ticket.cross_city_consultation_note && (
              <div className="rounded-lg border border-cyan-700/40 bg-cyan-900/20 p-3">
                <div className="mb-1 flex items-center gap-1.5">
                  <Lightbulb className="h-3.5 w-3.5 text-cyan-300" />
                  <p className="text-xs text-cyan-300">Онлайн-консультация</p>
                </div>
                <p className="text-sm leading-relaxed text-cyan-100">
                  {ticket.cross_city_consultation_note}
                </p>
              </div>
            )}
          </div>
        )}
      </Section>
    </div>
  );
}
