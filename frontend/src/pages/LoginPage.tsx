import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { KeyRound, RadioTower } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/use-auth";
import { toast } from "sonner";

export function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loginValue, setLoginValue] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: string })?.from ?? "/";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (mode === "register") {
        await register(username, email, password);
      } else {
        await login(loginValue || "admin", password);
      }
      navigate(from, { replace: true });
    } catch (err: any) {
      toast.error(err.message || "操作失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md">
        <form onSubmit={handleSubmit} className="space-y-6 rounded-2xl border border-border/75 bg-card/80 p-8 shadow-sm">
          <div className="text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary">
              <RadioTower className="h-5 w-5" aria-hidden="true" />
            </div>
            <h1 className="text-2xl font-semibold">今日看点</h1>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {mode === "register" ? "注册新账户" : "多主题实时信息聚合平台"}
            </p>
          </div>

          {mode === "register" && (
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="reg-username">用户名</Label>
                <Input id="reg-username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="用户名" autoFocus required />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="reg-email">邮箱 (选填)</Label>
                <Input id="reg-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email@example.com" />
              </div>
            </div>
          )}

          {mode === "login" && (
            <div className="space-y-1.5">
              <Label htmlFor="login-value">用户名或邮箱</Label>
              <Input id="login-value" value={loginValue} onChange={(e) => setLoginValue(e.target.value)} placeholder="用户名或邮箱" autoFocus />
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="login-password">密码</Label>
            <Input id="login-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="输入密码" required />
          </div>

          <Button type="submit" className="w-full gap-2" disabled={loading}>
            <KeyRound className="h-4 w-4" aria-hidden="true" />
            {loading ? "处理中..." : mode === "register" ? "注册" : "登录"}
          </Button>

          <p className="text-center text-xs text-muted-foreground">
            {mode === "login" ? (
              <>没有账户？<button type="button" className="underline hover:text-foreground" onClick={() => setMode("register")}>注册</button></>
            ) : (
              <>已有账户？<button type="button" className="underline hover:text-foreground" onClick={() => setMode("login")}>登录</button></>
            )}
          </p>
        </form>
      </div>
    </div>
  );
}
