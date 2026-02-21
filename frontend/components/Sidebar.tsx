"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Ticket, Users, Bot, Flame } from "lucide-react";
import clsx from "clsx";

const links = [
  { href: "/", label: "Дашборд", icon: LayoutDashboard },
  { href: "/tickets", label: "Обращения", icon: Ticket },
  { href: "/managers", label: "Менеджеры", icon: Users },
  { href: "/assistant", label: "AI Ассистент", icon: Bot },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-5 border-b border-gray-800">
        <Flame className="text-orange-500 w-6 h-6" />
        <span className="font-bold text-white text-lg tracking-tight">F.I.R.E.</span>
      </div>

      {/* Nav links */}
      <nav className="flex-1 flex flex-col gap-1 p-3 pt-4">
        {links.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={clsx(
              "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
              pathname === href
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:bg-gray-800 hover:text-white"
            )}
          >
            <Icon className="w-4 h-4 shrink-0" />
            {label}
          </Link>
        ))}
      </nav>

      <div className="p-4 text-xs text-gray-600 border-t border-gray-800">
        Freedom Finance © 2025
      </div>
    </aside>
  );
}
