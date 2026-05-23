import { Link, useLocation, useNavigate } from "react-router-dom";
import { FileText, Clock, Newspaper, LayoutDashboard, Settings, Tag, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";

const links = [
  { href: "/admin/sources", label: "数据源", icon: FileText },
  { href: "/admin/topics", label: "话题", icon: Tag },
  { href: "/admin/jobs", label: "任务", icon: Clock },
  { href: "/admin/highlights", label: "看点", icon: Newspaper },
  { href: "/admin/layout", label: "布局", icon: LayoutDashboard },
  { href: "/admin/settings", label: "设置", icon: Settings },
];

export function AdminSidebar() {
  const location = useLocation();
  const { logout } = useAuth();
  const navigate = useNavigate();

  return (
    <aside className="w-52 min-h-screen border-r bg-card/50 shrink-0">
      <div className="p-4">
        <Link to="/" className="text-sm font-bold tracking-tight text-muted-foreground hover:text-foreground transition-colors">
          ← 返回前台
        </Link>
      </div>
      <nav className="px-3 space-y-0.5">
        {links.map((l) => (
          <Link
            key={l.href}
            to={l.href}
            className={cn(
              "flex items-center gap-2.5 px-3 py-2 text-sm rounded-md transition-colors",
              location.pathname === l.href ? "bg-primary/10 text-primary font-medium" : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
          >
            <l.icon className="w-4 h-4" />
            {l.label}
          </Link>
        ))}
      </nav>
      <div className="absolute bottom-4 left-3 w-[184px]">
        <button
          onClick={() => { logout(); navigate("/login"); }}
          className="flex items-center gap-2.5 px-3 py-2 text-sm text-muted-foreground hover:text-foreground rounded-md w-full transition-colors"
        >
          <LogOut className="w-4 h-4" />
          退出登录
        </button>
      </div>
    </aside>
  );
}
