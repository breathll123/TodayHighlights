import { useQuery } from "@tanstack/react-query";
import { fetchAITokenUsages } from "@/api/client";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";

export function AdminAIUsagePage() {
  const { data, isLoading } = useQuery({ queryKey: ["ai-token-usages"], queryFn: () => fetchAITokenUsages(1, 20) });
  return (
    <div className="space-y-5">
      <AdminPageHeader eyebrow="AI Usage" title="AI 用量" description="查看用户、模型和场景的 token 使用记录。" />
      <div className="overflow-hidden rounded-lg border bg-card">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-muted-foreground">
            <tr><th className="px-4 py-3 text-left">用户</th><th className="px-4 py-3 text-left">模型</th><th className="px-4 py-3 text-left">场景</th><th className="px-4 py-3 text-right">Token</th></tr>
          </thead>
          <tbody>
            {isLoading ? <tr><td className="px-4 py-4" colSpan={4}>加载中</td></tr> : data?.items.map((item) => (
              <tr key={item.id} className="border-t">
                <td className="px-4 py-3">{item.user_id ?? "-"}</td>
                <td className="px-4 py-3">{item.model_name}</td>
                <td className="px-4 py-3">{item.usage_type}</td>
                <td className="px-4 py-3 text-right tabular-nums">{item.total_tokens}{item.estimated ? " 估算" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
