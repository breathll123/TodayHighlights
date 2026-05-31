import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { KeyRound, RadioTower } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/use-auth";
import { toast } from "sonner";

export function LoginPage() {
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(password);
      navigate("/admin/sources");
    } catch (err: any) {
      toast.error(err.message || "登录失败");
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
            <h1 className="text-2xl font-semibold">DataFlow</h1>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">多主题实时信息聚合平台 · 运营控制台</p>
          </div>
          <div className="space-y-2">
            <label htmlFor="admin-password" className="text-sm font-medium">管理密码</label>
            <Input
              id="admin-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
              autoFocus
            />
          </div>
          <Button type="submit" className="w-full gap-2" disabled={loading}>
            <KeyRound className="h-4 w-4" aria-hidden="true" />
            {loading ? "登录中..." : "登录"}
          </Button>
        </form>
      </div>
    </div>
  );
}
