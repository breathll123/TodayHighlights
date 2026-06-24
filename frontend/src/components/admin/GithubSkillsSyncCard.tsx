import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw, Star } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  fetchGithubSkillsStatus,
  setGithubSkillsSyncEnabled,
  triggerGithubSkillsSync,
  type GithubSkillsStatus,
} from "@/api/client";

function fmtTime(iso: string | null): string {
  if (!iso) return "尚未同步";
  return new Date(iso).toLocaleString("zh-CN", { hour12: false });
}

const STATUS_KEY = ["github-skills-status"];

export function GithubSkillsSyncCard() {
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: STATUS_KEY,
    queryFn: fetchGithubSkillsStatus,
    // While a sync runs, poll so counts + last-synced refresh on completion.
    refetchInterval: (query) => ((query.state.data as GithubSkillsStatus | undefined)?.running ? 3000 : false),
  });

  const apply = (next: GithubSkillsStatus) => queryClient.setQueryData(STATUS_KEY, next);

  const toggleMut = useMutation({
    mutationFn: setGithubSkillsSyncEnabled,
    onSuccess: (next) => { apply(next); toast.success(next.enabled ? "已开启每日自动同步" : "已关闭自动同步"); },
    onError: () => toast.error("操作失败"),
  });

  const syncMut = useMutation({
    mutationFn: triggerGithubSkillsSync,
    onSuccess: (next) => { apply(next); toast.success("已开始同步，完成后排行自动更新"); },
    onError: (err: { response?: { status?: number } }) =>
      toast.error(err?.response?.status === 409 ? "同步正在进行中" : "触发同步失败"),
  });

  const running = data?.running ?? false;
  const busy = running || syncMut.isPending;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Star className="h-4 w-4 text-amber-400" aria-hidden="true" />
          GitHub Skills 排行同步
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <div className="space-y-0.5">
            <Label className="text-sm">每日自动同步</Label>
            <p className="text-xs text-muted-foreground">
              每天 04:00 自动抓取 + AI 过滤 + 翻译；关闭后保留已有数据。
            </p>
          </div>
          <Switch
            checked={data?.enabled ?? false}
            onCheckedChange={(v) => toggleMut.mutate(v)}
            disabled={toggleMut.isPending || !data}
            aria-label="每日自动同步"
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-3">
          <div className="text-xs text-muted-foreground">
            {running ? (
              <span className="inline-flex items-center gap-1.5 text-primary">
                <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
                同步中…
              </span>
            ) : (
              <>
                <span className="tabular-nums">{data?.skill_count ?? 0}</span> 个 skill ·{" "}
                <span className="tabular-nums">{data?.repo_count ?? 0}</span> 候选 · 上次{" "}
                {fmtTime(data?.last_synced_at ?? null)}
              </>
            )}
          </div>
          <Button
            size="sm"
            variant="outline"
            disabled={busy || !data}
            onClick={() => syncMut.mutate()}
          >
            {busy ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <RefreshCw className="mr-1.5 h-3.5 w-3.5" aria-hidden="true" />
            )}
            立即同步
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
