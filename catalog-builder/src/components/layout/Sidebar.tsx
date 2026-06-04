import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Package,
  Type,
  Image,
  Globe,
  Layers,
  Download,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/catalog", label: "SKU Catalog", icon: Package },
  { to: "/copy", label: "Listing Copy", icon: Type },
  { to: "/carousel", label: "Carousel Designer", icon: Image },
  { to: "/html", label: "HTML Pages", icon: Globe },
  { to: "/bulk", label: "Bulk Operations", icon: Layers },
  { to: "/export", label: "Export Center", icon: Download },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  return (
    <aside className="flex h-full w-60 flex-col border-r border-slate-200 bg-white">
      <div className="px-5 py-4 border-b border-slate-100">
        <div className="text-base font-semibold text-slate-900 leading-tight">
          Amazon Catalogue
        </div>
        <div className="text-xs text-slate-500">& Store Builder</div>
      </div>

      <nav className="flex-1 overflow-y-auto p-3">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-brand-50 text-brand-700"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" aria-hidden />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-slate-100 p-4 text-xs text-slate-500">
        <div>Amazon India · No-Brand-Registry workflow</div>
        <div className="mt-1 font-mono">v0.1.0</div>
      </div>
    </aside>
  );
}
