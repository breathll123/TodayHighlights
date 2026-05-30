import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { KeyRound } from "lucide-react";
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
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-sm">
        <form onSubmit={handleSubmit} className="bg-card border rounded-xl shadow-sm p-8 space-y-5">
          <div className="text-center">
            <div className="w-12 h-12 bg-muted rounded-xl flex items-center justify-center mx-auto mb-4">
              <KeyRound className="w-6 h-6 text-muted-foreground" />
            </div>
            <h1 className="text-xl font-bold">DataFlow</h1>
            <p className="text-sm text-muted-foreground mt-1">管理后台 · 数据看板配置</p>
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
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "登录中..." : "登录"}
          </Button>
        </form>
      </div>
    </div>
  );
}
