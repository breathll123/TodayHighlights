import { Link, useLocation } from "react-router-dom";
import { Sun, Moon } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function Navbar() {
  const { theme, setTheme } = useTheme();
  const location = useLocation();
  const isAdmin = location.pathname.startsWith("/admin");

  return (
    <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur">
      <div className="flex h-14 items-center justify-between px-6 max-w-6xl mx-auto">
        <div className="flex items-center gap-8">
          <Link to="/" className="text-lg font-bold">今日看点</Link>
          <nav className="flex items-center gap-1">
            <Link to="/" className={cn("px-3 py-1.5 text-sm rounded-md hover:bg-muted transition-colors", !isAdmin && "bg-muted")}>摘要</Link>
            <Link to="/topics/stocks" className="px-3 py-1.5 text-sm rounded-md hover:bg-muted transition-colors">股票</Link>
            <Link to="/admin/sources" className={cn("px-3 py-1.5 text-sm rounded-md hover:bg-muted transition-colors", isAdmin && "bg-muted")}>管理</Link>
          </nav>
        </div>
        <Button variant="ghost" size="icon" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
          <Sun className="h-4 w-4 rotate-0 scale-100 transition-transform dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-transform dark:rotate-0 dark:scale-100" />
        </Button>
      </div>
    </header>
  );
}
