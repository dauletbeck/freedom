"use client";

import { MapContainer, TileLayer, CircleMarker, Popup, Polyline } from "react-leaflet";
import "leaflet/dist/leaflet.css";

// Light-theme colours
const LIGHT = {
  tile: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
  segment: { VIP: "#92400E", Priority: "#1E40AF", Mass: "#374151" } as Record<string, string>,
  office: { fill: "#EA580C", stroke: "#C2410C" },
  route: { primary: "#0066CC", alternative: "#E85D04" },
};

// Dark-theme colours
const DARK = {
  tile: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
  segment: { VIP: "#FCD34D", Priority: "#60A5FA", Mass: "#9CA3AF" } as Record<string, string>,
  office: { fill: "#FB923C", stroke: "#F97316" },
  route: { primary: "#64B5F6", alternative: "#FFB74D" },
};

function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

interface Office {
  id: number;
  office_name: string;
  address?: string;
  latitude?: number;
  longitude?: number;
}

interface Ticket {
  id: number;
  guid: string;
  segment?: string;
  city?: string;
  skill_gap_routing_note?: string;
  analysis?: {
    client_lat?: number;
    client_lon?: number;
    ticket_type?: string;
    language?: string;
    sentiment?: string;
  };
  assignment?: {
    assigned_office?: string;
    manager?: { full_name?: string };
  };
}

interface MapViewProps {
  offices: Office[];
  tickets: Ticket[];
  dark?: boolean;
  showOffices?: boolean;
  showTickets?: boolean;
  showRoutes?: boolean;
  showAlternatives?: boolean;
}

export default function MapView({
  offices,
  tickets,
  dark = false,
  showOffices = false,
  showTickets = false,
  showRoutes = false,
  showAlternatives = false,
}: MapViewProps) {
  const theme = dark ? DARK : LIGHT;

  const officesWithCoords = offices.filter((o) => o.latitude != null && o.longitude != null);

  // Build name → office lookup for route line destinations
  const officeByName = new Map(officesWithCoords.map((o) => [o.office_name, o]));

  const ticketsWithCoords = tickets.filter(
    (t) => t.analysis?.client_lat != null && t.analysis?.client_lon != null
  );

  // Find nearest office from the offices array (client-side, mirrors backend logic)
  function findNearestOffice(lat: number, lon: number): Office | null {
    let nearest: Office | null = null;
    let minDist = Infinity;
    for (const o of officesWithCoords) {
      const d = haversineKm(lat, lon, o.latitude!, o.longitude!);
      if (d < minDist) {
        minDist = d;
        nearest = o;
      }
    }
    return nearest;
  }

  return (
    <MapContainer
      center={[48.0, 66.0]}
      zoom={5}
      style={{ height: "100%", width: "100%" }}
      zoomControl={true}
    >
      <TileLayer
        key={dark ? "dark" : "light"}
        attribution='&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url={theme.tile}
      />

      {/* Primary routes: client → assigned office */}
      {showRoutes &&
        ticketsWithCoords.map((ticket) => {
          const assignedOffice = officeByName.get(ticket.assignment?.assigned_office ?? "");
          if (!assignedOffice) return null;
          return (
            <Polyline
              key={`route-${ticket.id}`}
              positions={[
                [ticket.analysis!.client_lat!, ticket.analysis!.client_lon!],
                [assignedOffice.latitude!, assignedOffice.longitude!],
              ]}
              pathOptions={{
                color: theme.route.primary,
                weight: 1.8,
                opacity: 0.55,
              }}
            />
          );
        })}

      {/* Alternative routes: client → nearest office (only when skill gap exists) */}
      {showAlternatives &&
        ticketsWithCoords
          .filter((t) => t.skill_gap_routing_note)
          .map((ticket) => {
            const nearest = findNearestOffice(
              ticket.analysis!.client_lat!,
              ticket.analysis!.client_lon!
            );
            if (!nearest) return null;
            return (
              <Polyline
                key={`alt-${ticket.id}`}
                positions={[
                  [ticket.analysis!.client_lat!, ticket.analysis!.client_lon!],
                  [nearest.latitude!, nearest.longitude!],
                ]}
                pathOptions={{
                  color: theme.route.alternative,
                  weight: 1.8,
                  opacity: 0.7,
                  dashArray: "7 5",
                }}
              />
            );
          })}

      {/* Office markers — larger circles */}
      {showOffices &&
        officesWithCoords.map((office) => (
          <CircleMarker
            key={office.id}
            center={[office.latitude!, office.longitude!]}
            radius={14}
            pathOptions={{
              color: theme.office.stroke,
              fillColor: theme.office.fill,
              fillOpacity: 0.95,
              weight: 2.5,
            }}
          >
            <Popup>
              <div className="text-sm">
                <p className="font-bold">{office.office_name}</p>
                {office.address && (
                  <p className="text-gray-600 mt-0.5">{office.address}</p>
                )}
              </div>
            </Popup>
          </CircleMarker>
        ))}

      {/* Ticket markers — small circles coloured by segment */}
      {showTickets &&
        ticketsWithCoords.map((ticket) => {
          const color =
            theme.segment[ticket.segment ?? "Mass"] ?? theme.segment.Mass;
          return (
            <CircleMarker
              key={ticket.id}
              center={[ticket.analysis!.client_lat!, ticket.analysis!.client_lon!]}
              radius={5}
              pathOptions={{ color, fillColor: color, fillOpacity: 0.85, weight: 1 }}
            >
              <Popup>
                <div className="text-sm space-y-0.5">
                  <p className="font-mono font-bold">{ticket.guid?.slice(0, 8)}</p>
                  <p>Сегмент: {ticket.segment ?? "—"}</p>
                  <p>Тип: {ticket.analysis?.ticket_type ?? "—"}</p>
                  <p>Город: {ticket.city ?? "—"}</p>
                  <p>Офис: {ticket.assignment?.assigned_office ?? "—"}</p>
                  <p>Менеджер: {ticket.assignment?.manager?.full_name ?? "—"}</p>
                  {ticket.skill_gap_routing_note && (
                    <p className="text-orange-600 font-medium mt-1">⚠ Резервный офис</p>
                  )}
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
    </MapContainer>
  );
}
