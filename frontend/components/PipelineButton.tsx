"use client";

import { useState } from "react";
import { Play, Loader2, CheckCircle2, Trash2 } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function PipelineButton({ onComplete }: { onComplete?: () => void }) {
  const [state, setState] = useState<"idle" | "running" | "done">("idle");
  const [progress, setProgress] = useState({ current: 0, total: 0, guid: "" });
  const [error, setError] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);

  const run = async () => {
    setState("running");
    setError(null);
    try {
      await fetch(`${API}/api/pipeline/run`, { method: "POST" });

      const poll = setInterval(async () => {
        const res = await fetch(`${API}/api/pipeline/status`);
        const data = await res.json();
        setProgress({ current: data.progress, total: data.total, guid: data.current });

        if (!data.running) {
          clearInterval(poll);
          if (data.error) {
            setError(data.error);
            setState("idle");
          } else {
            setState("done");
            onComplete?.();
          }
        }
      }, 1500);
    } catch (e: any) {
      setError(e.message);
      setState("idle");
    }
  };

  const reset = async () => {
    if (!confirm("Сбросить базу данных? Все результаты анализа будут удалены.")) return;
    setResetting(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/pipeline/reset`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Reset failed");
      }
      setState("idle");
      onComplete?.();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={reset}
        disabled={resetting || state === "running"}
        className="flex items-center gap-2 px-4 py-2 bg-red-900/60 hover:bg-red-800 disabled:opacity-40 text-red-300 hover:text-white text-sm font-medium rounded-lg transition-colors border border-red-800/60"
      >
        {resetting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
        {resetting ? "Сброс..." : "Сбросить БД"}
      </button>

      <button
        onClick={run}
        disabled={state === "running" || resetting}
        className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
      >
        {state === "running" ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : state === "done" ? (
          <CheckCircle2 className="w-4 h-4" />
        ) : (
          <Play className="w-4 h-4" />
        )}
        {state === "running" ? "Обработка..." : state === "done" ? "Готово!" : "Запустить пайплайн"}
      </button>

      {state === "running" && progress.total > 0 && (
        <span className="text-xs text-gray-400">
          {progress.current}/{progress.total} — {progress.guid?.slice(0, 8)}...
        </span>
      )}
      {error && <span className="text-xs text-red-400">{error}</span>}
    </div>
  );
}
