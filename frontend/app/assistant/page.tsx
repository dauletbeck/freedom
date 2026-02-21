"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, BarChart2, Loader2 } from "lucide-react";
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis,
  Tooltip, ResponsiveContainer, LineChart, Line,
} from "recharts";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const COLORS = ["#3b82f6","#10b981","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#f97316","#ec4899"];

const EXAMPLE_QUERIES = [
  "Покажи распределение типов обращений",
  "Какие офисы получили больше всего обращений?",
  "Распределение по языкам",
  "Топ 10 менеджеров по нагрузке",
  "Соотношение сегментов VIP, Priority, Mass",
];

interface Message {
  role: "user" | "assistant";
  text: string;
  chartType?: string;
  chartData?: { labels: string[]; values: number[]; title?: string };
  sql?: string;
}

function ChartBlock({ type, data }: { type: string; data: any }) {
  if (!data?.labels?.length) return null;
  const chartData = data.labels.map((l: string, i: number) => ({ name: l, value: data.values[i] ?? 0 }));

  return (
    <div className="mt-3 bg-gray-950 rounded-lg p-4 border border-gray-800">
      {data.title && <p className="text-xs text-gray-500 mb-3">{data.title}</p>}
      <ResponsiveContainer width="100%" height={200}>
        {type === "pie" ? (
          <PieChart>
            <Pie data={chartData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70}
              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
              {chartData.map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8 }} />
          </PieChart>
        ) : type === "line" ? (
          <LineChart data={chartData}>
            <XAxis dataKey="name" tick={{ fill: "#6b7280", fontSize: 11 }} />
            <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8 }} />
            <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} dot={false} />
          </LineChart>
        ) : (
          <BarChart data={chartData}>
            <XAxis dataKey="name" tick={{ fill: "#6b7280", fontSize: 10 }} angle={-20} textAnchor="end" height={40} />
            <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#1f2937", border: "1px solid #374151", borderRadius: 8 }} />
            <Bar dataKey="value" radius={[4, 4, 0, 0]}>
              {chartData.map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Bar>
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      text: "Привет! Я AI-ассистент системы FIRE. Задайте мне вопрос о распределении обращений, и я построю нужный график.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (query?: string) => {
    const q = query ?? input.trim();
    if (!q || loading) return;
    setInput("");

    setMessages((m) => [...m, { role: "user", text: q }]);
    setLoading(true);

    try {
      const res = await fetch(`${API}/api/assistant`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q }),
      });
      const data = await res.json();
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: data.answer,
          chartType: data.chart_type,
          chartData: data.chart_data,
          sql: data.sql,
        },
      ]);
    } catch (e: any) {
      setMessages((m) => [...m, { role: "assistant", text: `Ошибка: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full max-w-3xl mx-auto">
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Bot className="w-6 h-6 text-blue-400" /> AI Ассистент
        </h1>
        <p className="text-sm text-gray-500 mt-0.5">Задавайте вопросы и получайте графики</p>
      </div>

      {/* Example queries */}
      <div className="flex gap-2 flex-wrap mb-4">
        {EXAMPLE_QUERIES.map((q) => (
          <button
            key={q}
            onClick={() => send(q)}
            disabled={loading}
            className="text-xs px-3 py-1.5 rounded-full border border-gray-700 text-gray-400 hover:border-blue-500 hover:text-blue-400 transition-colors disabled:opacity-50"
          >
            {q}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
              msg.role === "user" ? "bg-blue-600" : "bg-gray-700"
            }`}>
              {msg.role === "user" ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>
            <div className={`flex-1 max-w-[85%] ${msg.role === "user" ? "items-end" : "items-start"} flex flex-col`}>
              <div className={`rounded-xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-blue-600 text-white rounded-tr-sm"
                  : "bg-gray-900 border border-gray-800 text-gray-200 rounded-tl-sm"
              }`}>
                {msg.text}
              </div>
              {msg.chartData && msg.chartType && (
                <div className="w-full">
                  <ChartBlock type={msg.chartType} data={msg.chartData} />
                </div>
              )}
              {msg.sql && (
                <details className="mt-2 w-full">
                  <summary className="text-xs text-gray-600 cursor-pointer hover:text-gray-400">SQL запрос</summary>
                  <pre className="mt-1 text-xs text-gray-500 bg-gray-950 border border-gray-800 rounded p-2 overflow-x-auto">
                    {msg.sql}
                  </pre>
                </details>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl rounded-tl-sm px-4 py-3">
              <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex gap-3 pt-4 border-t border-gray-800">
        <input
          className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
          placeholder="Например: покажи распределение типов обращений по офисам..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          disabled={loading}
        />
        <button
          onClick={() => send()}
          disabled={loading || !input.trim()}
          className="px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-xl text-white transition-colors"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
}
