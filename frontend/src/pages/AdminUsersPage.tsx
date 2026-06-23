import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchAdminUsers, updateAdminUserStatus } from "@/api/client";
import { AdminPageHeader } from "@/components/admin/AdminPageHeader";
import { TableSkeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

export function AdminUsersPage() {
  const queryClient = useQueryClient();
  const { data: users = [], isLoading } = useQuery({ queryKey: ["admin-users"], queryFn: fetchAdminUsers });
  const mutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: "active" | "disabled" }) => updateAdminUserStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  });

  return (
    <div className="space-y-5">
      <AdminPageHeader eyebrow="Users" title="用户管理" description="查看注册用户并启用或禁用 AI 使用权限。" />
      <div className="overflow-x-auto rounded-lg border bg-card">
        <table className="w-full min-w-[480px] text-sm stagger-rows">
          <thead className="bg-muted/50 text-muted-foreground">
            <tr><th className="px-4 py-3 text-left">用户</th><th className="px-4 py-3 text-left">角色</th><th className="px-4 py-3 text-left">状态</th><th className="px-4 py-3 text-right">操作</th></tr>
          </thead>
          {isLoading ? <TableSkeleton columns={4} rows={5} /> : (
          <tbody>
            {users.map((user) => (
              <tr key={user.id} className="border-t">
                <td className="px-4 py-3">{user.username}</td>
                <td className="px-4 py-3">{user.role}</td>
                <td className="px-4 py-3">{user.status}</td>
                <td className="px-4 py-3 text-right">
                  <Button size="sm" variant="outline" onClick={() => mutation.mutate({ id: user.id, status: user.status === "active" ? "disabled" : "active" })}>
                    {user.status === "active" ? "禁用" : "启用"}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
          )}
        </table>
      </div>
    </div>
  );
}
