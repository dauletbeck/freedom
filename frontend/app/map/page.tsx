"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { Sun, Moon } from "lucide-react";
import clsx from "clsx";

const MapView = dynamic(() => import("@/components/MapView"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full text-gray-500">
      Загрузка карты...
    </div>
  ),
});

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Legend colours mirror MapView theme constants
const LEGEND = {
  light: {
    office: "bg-orange-600",
    vip: "bg-amber-800",
    priority: "bg-blue-800",
    mass: "bg-gray-700",
  },
  dark: {
    office: "bg-orange-400",
    vip: "bg-amber-300",
    priority: "bg-blue-400",
    mass: "bg-gray-400",
  },
};

interface LayerBtn {
  key: "offices" | "tickets" | "routes" | "alternatives";
  label: string;
  activeClass: string;
}

const LAYER_BTNS: LayerBtn[] = [
  { key: "offices",      label: "Офисы",        activeClass: "bg-orange-600 text-white border-orange-600" },
  { key: "tickets",      label: "Обращения",    activeClass: "bg-indigo-600 text-white border-indigo-600" },
  { key: "routes",       label: "Маршруты",     activeClass: "bg-blue-600 text-white border-blue-600" },
  { key: "alternatives", label: "Альтернативы", activeClass: "bg-amber-600 text-white border-amber-600" },
];

export default function MapPage() {
  const [offices, setOffices] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dark, setDark] = useState(false);

  const [showOffices, setShowOffices] = useState(true);
  const [showTickets, setShowTickets] = useState(true);
  const [showRoutes, setShowRoutes] = useState(true);
  const [showAlternatives, setShowAlternatives] = useState(false);

  const layerState = {
    offices: showOffices,
    tickets: showTickets,
    routes: showRoutes,
    alternatives: showAlternatives,
  };

  const layerToggle = {
    offices: () => setShowOffices((v) => !v),
    tickets: () => setShowTickets((v) => !v),
    routes: () => setShowRoutes((v) => !v),
    alternatives: () => setShowAlternatives((v) => !v),
  };

  useEffect(() => {
    Promise.all([
      fetch(`${API}/api/business-units`).then((r) => r.json()),
      fetch(`${API}/api/tickets?limit=1000`).then((r) => r.json()),
    ]).then(([officesData, ticketsData]) => {
      setOffices(officesData);
      setTickets(ticketsData);
      setLoading(false);
    });
  }, []);

  const ticketsWithCoords = tickets.filter(
    (t: any) => t.analysis?.client_lat != null && t.analysis?.client_lon != null
  );
  const ticketsWithSkillGap = tickets.filter((t: any) => t.skill_gap_routing_note);

  const legend = dark ? LEGEND.dark : LEGEND.light;

  return (
    <div className="flex flex-col gap-3" style={{ height: "calc(100vh - 3rem)" }}>
      {/* Header */}
      <div className="flex items-center justify-between shrink-0 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Карта</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {offices.length} офисов · {ticketsWithCoords.length} обращений с координатами
            {ticketsWithSkillGap.length > 0 && (
              <span className="ml-1 text-amber-500">
                · {ticketsWithSkillGap.length} с резервным офисом
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-4 flex-wrap">
          {/* Layer toggles */}
          <div className="flex items-center gap-1.5">
            {LAYER_BTNS.map(({ key, label, activeClass }) => (
              <button
                key={key}
                onClick={layerToggle[key]}
                className={clsx(
                  "px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors",
                  layerState[key]
                    ? activeClass
                    : "bg-gray-900 text-gray-400 border-gray-700 hover:bg-gray-800 hover:text-white"
                )}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Legend */}
          <div className="flex items-center gap-4 text-xs text-gray-400">
            <span className="flex items-center gap-1.5">
              <span className={`inline-block w-3.5 h-3.5 rounded-full ${legend.office}`} />
              Офис
            </span>
            <span className="flex items-center gap-1.5">
              <span className={`inline-block w-3 h-3 rounded-full ${legend.vip}`} />
              VIP
            </span>
            <span className="flex items-center gap-1.5">
              <span className={`inline-block w-3 h-3 rounded-full ${legend.priority}`} />
              Priority
            </span>
            <span className="flex items-center gap-1.5">
              <span className={`inline-block w-3 h-3 rounded-full ${legend.mass}`} />
              Mass
            </span>
            <span className="flex items-center gap-1.5">
              <svg width="16" height="6" className="shrink-0">
                <line x1="0" y1="3" x2="16" y2="3" stroke={dark ? "#64B5F6" : "#0066CC"} strokeWidth="2" />
              </svg>
              Маршрут
            </span>
            <span className="flex items-center gap-1.5">
              <svg width="16" height="6" className="shrink-0">
                <line x1="0" y1="3" x2="16" y2="3" stroke={dark ? "#FFB74D" : "#E85D04"} strokeWidth="2" strokeDasharray="4 3" />
              </svg>
              Альтернатива
            </span>
          </div>

          {/* Theme toggle */}
          <button
            onClick={() => setDark((d) => !d)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-800 text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
            title={dark ? "Светлая тема" : "Тёмная тема"}
          >
            {dark ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
            {dark ? "Светлая" : "Тёмная"}
          </button>
        </div>
      </div>

      {/* Map */}
      <div className="flex-1 min-h-0 rounded-xl overflow-hidden border border-gray-800">
        {loading ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            Загрузка данных...
          </div>
        ) : (
          <MapView
            offices={offices}
            tickets={tickets}
            dark={dark}
            showOffices={showOffices}
            showTickets={showTickets}
            showRoutes={showRoutes}
            showAlternatives={showAlternatives}
          />
        )}
      </div>
    </div>
  );
}
