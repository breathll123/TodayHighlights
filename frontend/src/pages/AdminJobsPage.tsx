import { useQuery } from "@tanstack/react-query";
import { fetchJobs } from "../api/client";

export function AdminJobsPage() {
  const { data: jobs, isLoading } = useQuery({ queryKey: ["jobs"], queryFn: fetchJobs, refetchInterval: 5000 });

  if (isLoading) return <div className="page-message">加载中...</div>;

  return (
    <div className="page">
      <h1>任务日志</h1>
      <table className="admin-table">
        <thead>
          <tr><th>ID</th><th>数据源</th><th>触发</th><th>状态</th><th>发现</th><th>保存</th><th>错误</th><th>开始</th><th>结束</th></tr>
        </thead>
        <tbody>
          {jobs?.map((j) => (
            <tr key={j.id} className={j.status === "failed" ? "row-error" : j.status === "success" ? "row-success" : ""}>
              <td>{j.id}</td>
              <td>{j.source_id}</td>
              <td>{j.trigger_type}</td>
              <td>{j.status}</td>
              <td>{j.items_found}</td>
              <td>{j.items_saved}</td>
              <td className="error-cell">{j.error_message?.slice(0, 60)}</td>
              <td>{j.started_at ? new Date(j.started_at).toLocaleTimeString() : "-"}</td>
              <td>{j.finished_at ? new Date(j.finished_at).toLocaleTimeString() : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
