import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Activity, ChevronDown, Moon, RadioTower, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { fetchTopics } from "@/api/client";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function PublicNavbar() {
  const { theme, setTheme } = useTheme();
  const location = useLocation();
  const { data: topicItems = [] } = useQuery({ queryKey: ["public-topics"], queryFn: fetchTopics });
  const topics = [
    { href: "/", label: "全局" },
    ...topicItems
      .filter((topic) => topic.enabled !== false)
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((topic) => ({
        href: `/topics/${topic.slug}`,
        label: topic.name,
      })),
  ];

  return (
    <header className="sticky top-0 z-50 border-b border-border/70 bg-background/88 backdrop-blur-xl">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-[60] focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground"
      >
        跳到主要内容
      </a>
      <div className="mx-auto flex h-16 max-w-[1500px] items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-5">
          <Link to="/" className="flex items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-primary/25 bg-primary/12 text-primary shadow-[0_0_24px_hsl(var(--primary)/0.12)]">
              <RadioTower className="h-4 w-4" aria-hidden="true" />
            </span>
            <span className="leading-tight">
              <span className="block text-base font-semibold">今日看点</span>
              <span className="hidden text-[11px] font-medium uppercase text-muted-foreground sm:block">Signal Hub</span>
            </span>
          </Link>

          <nav className="hidden items-center rounded-lg border border-border/70 bg-card/70 p-1 md:flex" aria-label="主题导航">
            {topics.map((topic) => {
              const active = location.pathname === topic.href;
              return (
                <Link
                  key={topic.href}
                  to={topic.href}
                  className={cn(
                    "inline-flex h-9 items-center rounded-md px-3 text-sm font-medium transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    active ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground"
                  )}
                >
                  {topic.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex items-center gap-2">
          <div className="hidden items-center gap-2 rounded-lg border border-border/70 bg-card/70 px-3 py-2 text-xs text-muted-foreground lg:flex">
            <Activity className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
            <span>多主题实时聚合</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            aria-label="切换主题"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            <Sun className="h-4 w-4 rotate-0 scale-100 transition-transform dark:-rotate-90 dark:scale-0" aria-hidden="true" />
            <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-transform dark:rotate-0 dark:scale-100" aria-hidden="true" />
          </Button>
        </div>
      </div>

      <div className="border-t border-border/60 px-4 py-2 md:hidden">
        <div className="flex items-center gap-2 overflow-x-auto">
          <span className="inline-flex items-center gap-1 rounded-md border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground">
            <ChevronDown className="h-3 w-3" aria-hidden="true" />
            主题
          </span>
          {topics.map((topic) => (
            <Link
              key={topic.href}
              to={topic.href}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm",
                location.pathname === topic.href ? "bg-primary text-primary-foreground" : "bg-card text-muted-foreground"
              )}
            >
              {topic.label}
            </Link>
          ))}
        </div>
      </div>
    </header>
  );
}
