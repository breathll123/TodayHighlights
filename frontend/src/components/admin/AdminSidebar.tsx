import { Link, useLocation, useNavigate } from "react-router-dom";
import { BrainCircuit, Clock, FileText, Gauge, LayoutDashboard, LogOut, Newspaper, RadioTower, ScrollText, Settings, Tag, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";

const links = [
  { href: "/admin/sources", label: "数据源", icon: FileText },
  { href: "/admin/topics", label: "话题", icon: Tag },
  { href: "/admin/jobs", label: "任务", icon: Clock },
  { href: "/admin/ai-jobs", label: "AI 任务", icon: BrainCircuit },
  { href: "/admin/users", label: "用户", icon: Users },
  { href: "/admin/ai-usage", label: "AI 用量", icon: Gauge },
  { href: "/admin/ai-prompts", label: "Prompt 模板", icon: ScrollText },
  { href: "/admin/highlights", label: "看点", icon: Newspaper },
  { href: "/admin/layout", label: "布局", icon: LayoutDashboard },
  { href: "/admin/settings", label: "设置", icon: Settings },
];

export function AdminSidebar() {
  const location = useLocation();
  const { logout } = useAuth();
  const navigate = useNavigate();

  return (
    <aside className="sticky top-0 h-screen w-16 shrink-0 border-r border-border/70 bg-card/75 md:w-60">
      <div className="border-b border-border/70 p-4">
        <Link to="/" className="flex items-center gap-3 rounded-lg p-1.5 transition-colors hover:bg-muted/50">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-primary/25 bg-primary/10 text-primary">
            <RadioTower className="h-4 w-4" aria-hidden="true" />
          </span>
          <span className="hidden md:block">
            <span className="block text-sm font-semibold text-foreground">DataFlow</span>
            <span className="block text-[11px] font-medium uppercase text-muted-foreground">Ops Console</span>
          </span>
        </Link>
      </div>
      <nav className="space-y-1 px-3 py-4" aria-label="后台导航">
        {links.map((l) => (
          <Link
            key={l.href}
            to={l.href}
            title={l.label}
            className={cn(
              "flex min-h-10 items-center justify-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:justify-start",
              location.pathname === l.href
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:bg-muted/70 hover:text-foreground"
            )}
          >
            <l.icon className="h-4 w-4" aria-hidden="true" />
            <span className="hidden md:inline">{l.label}</span>
          </Link>
        ))}
      </nav>
      <div className="absolute bottom-4 left-3 right-3">
        <Link
          to="/"
          className="mb-2 hidden min-h-10 items-center rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted/70 hover:text-foreground md:flex"
        >
          返回前台
        </Link>
        <button
          onClick={() => { logout(); navigate("/login"); }}
          title="退出登录"
          className="flex min-h-10 w-full items-center justify-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted/70 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:justify-start"
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
          <span className="hidden md:inline">退出登录</span>
        </button>
      </div>
    </aside>
  );
}
