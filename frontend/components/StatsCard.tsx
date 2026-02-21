import clsx from "clsx";
import { LucideIcon } from "lucide-react";

interface Props {
  title: string;
  value: string | number;
  sub?: string;
  icon: LucideIcon;
  color?: "blue" | "green" | "orange" | "purple" | "red";
}

const colorMap: Record<string, string> = {
  blue: "bg-blue-500/10 text-blue-400",
  green: "bg-green-500/10 text-green-400",
  orange: "bg-orange-500/10 text-orange-400",
  purple: "bg-purple-500/10 text-purple-400",
  red: "bg-red-500/10 text-red-400",
};

export default function StatsCard({ title, value, sub, icon: Icon, color = "blue" }: Props) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-start gap-4">
      <div className={clsx("p-2.5 rounded-lg", colorMap[color])}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{title}</p>
        <p className="text-2xl font-bold text-white">{value}</p>
        {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}
