import { useQuery } from "@tanstack/react-query";
import { fetchJobs } from "../api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function AdminJobsPage() {
  const { data: jobs, isLoading } = useQuery({ queryKey: ["jobs"], queryFn: fetchJobs, refetchInterval: 5000 });

  if (isLoading) return <div className="text-center py-12 text-muted-foreground">加载中...</div>;

  const statusVariant = (status: string) => {
    if (status === "failed") return "destructive";
    if (status === "success") return "default";
    return "secondary";
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">任务日志</h1>

      <Card>
        <CardHeader>
          <CardTitle>爬取任务列表</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-4 py-3 text-left font-medium">ID</th>
                  <th className="px-4 py-3 text-left font-medium">数据源</th>
                  <th className="px-4 py-3 text-left font-medium">触发</th>
                  <th className="px-4 py-3 text-left font-medium">状态</th>
                  <th className="px-4 py-3 text-left font-medium">发现</th>
                  <th className="px-4 py-3 text-left font-medium">保存</th>
                  <th className="px-4 py-3 text-left font-medium">错误</th>
                  <th className="px-4 py-3 text-left font-medium">开始</th>
                  <th className="px-4 py-3 text-left font-medium">结束</th>
                </tr>
              </thead>
              <tbody>
                {jobs?.map((j) => (
                  <tr key={j.id} className={`border-b last:border-0 ${j.status === "failed" ? "bg-red-50 dark:bg-red-950/30" : j.status === "success" ? "bg-green-50 dark:bg-green-950/30" : ""}`}>
                    <td className="px-4 py-3">{j.id}</td>
                    <td className="px-4 py-3">{j.source_id}</td>
                    <td className="px-4 py-3">{j.trigger_type}</td>
                    <td className="px-4 py-3">
                      <Badge variant={statusVariant(j.status)}>{j.status}</Badge>
                    </td>
                    <td className="px-4 py-3">{j.items_found}</td>
                    <td className="px-4 py-3">{j.items_saved}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground max-w-[120px] truncate" title={j.error_message}>{j.error_message?.slice(0, 60)}</td>
                    <td className="px-4 py-3">{j.started_at ? new Date(j.started_at).toLocaleTimeString() : "-"}</td>
                    <td className="px-4 py-3">{j.finished_at ? new Date(j.finished_at).toLocaleTimeString() : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
