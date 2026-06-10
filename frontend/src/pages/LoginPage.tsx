import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { KeyRound, LoaderCircle, RadioTower, RefreshCw } from "lucide-react";
import { fetchSetupStatus } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/use-auth";
import { toast } from "sonner";

type PageMode = "loading" | "bootstrap" | "login" | "error";

export function LoginPage() {
  const [mode, setMode] = useState<PageMode>("loading");
  const [loginValue, setLoginValue] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const { login, bootstrapAdmin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: string })?.from ?? "/";

  const checkSetupStatus = useCallback(async () => {
    setMode("loading");
    try {
      const status = await fetchSetupStatus();
      setMode(status.setup_required ? "bootstrap" : "login");
    } catch {
      setMode("error");
    }
  }, []);

  useEffect(() => {
    void checkSetupStatus();
  }, [checkSetupStatus]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (mode === "bootstrap" && password !== passwordConfirmation) {
      toast.error("两次输入的密码不一致");
      return;
    }

    setSubmitting(true);
    try {
      if (mode === "bootstrap") {
        await bootstrapAdmin(username, email, password);
      } else {
        await login(loginValue, password);
      }
      navigate(from, { replace: true });
    } catch (error) {
      const err = error as Error & { status?: number };
      if (mode === "bootstrap" && err.status === 409) {
        setMode("login");
        setPassword("");
        setPasswordConfirmation("");
        toast.error("系统已完成初始化，请使用管理员账户登录");
      } else {
        toast.error(err.message || "操作失败");
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (mode === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
          <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
          正在检查系统状态...
        </div>
      </div>
    );
  }

  if (mode === "error") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="w-full max-w-md space-y-5 rounded-2xl border border-border/75 bg-card/80 p-8 text-center shadow-sm">
          <div>
            <h1 className="text-xl font-semibold">无法检查系统初始化状态</h1>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              为避免意外开放管理员创建入口，请确认后端服务和数据库已启动后重试。
            </p>
          </div>
          <Button type="button" className="w-full gap-2" onClick={() => void checkSetupStatus()}>
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            重试
          </Button>
        </div>
      </div>
    );
  }

  const isBootstrap = mode === "bootstrap";

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md">
        <form onSubmit={handleSubmit} className="space-y-6 rounded-2xl border border-border/75 bg-card/80 p-8 shadow-sm">
          <div className="text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary">
              <RadioTower className="h-5 w-5" aria-hidden="true" />
            </div>
            <h1 className="text-2xl font-semibold">{isBootstrap ? "创建管理员账户" : "管理员登录"}</h1>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {isBootstrap ? "首次使用需要创建唯一的初始管理员" : "今日看点管理后台"}
            </p>
          </div>

          {isBootstrap && (
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="reg-username">用户名</Label>
                <Input id="reg-username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="至少 2 个字符" minLength={2} maxLength={80} autoFocus required />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="reg-email">邮箱 (选填)</Label>
                <Input id="reg-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email@example.com" maxLength={160} />
              </div>
            </div>
          )}

          {!isBootstrap && (
            <div className="space-y-1.5">
              <Label htmlFor="login-value">用户名或邮箱</Label>
              <Input id="login-value" value={loginValue} onChange={(e) => setLoginValue(e.target.value)} placeholder="用户名或邮箱" minLength={2} maxLength={160} autoFocus required />
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="login-password">密码</Label>
            <Input id="login-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="至少 6 个字符" minLength={6} maxLength={128} required />
          </div>

          {isBootstrap && (
            <div className="space-y-1.5">
              <Label htmlFor="password-confirmation">确认密码</Label>
              <Input
                id="password-confirmation"
                type="password"
                value={passwordConfirmation}
                onChange={(e) => setPasswordConfirmation(e.target.value)}
                placeholder="再次输入密码"
                minLength={6}
                maxLength={128}
                required
              />
            </div>
          )}

          <Button type="submit" className="w-full gap-2" disabled={submitting}>
            <KeyRound className="h-4 w-4" aria-hidden="true" />
            {submitting ? "处理中..." : isBootstrap ? "创建管理员" : "登录"}
          </Button>

          {isBootstrap && (
            <p className="text-center text-xs leading-5 text-muted-foreground">
              创建成功后，公开管理员注册入口将自动关闭。
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
