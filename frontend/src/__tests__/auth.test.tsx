import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/api/client";
import { AuthProvider, useAuth } from "@/hooks/use-auth";
import { LoginPage } from "@/pages/LoginPage";

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}

function renderLoginPage() {
  return render(
    <MemoryRouter>
      <Wrapper>
        <LoginPage />
      </Wrapper>
    </MemoryRouter>
  );
}

function AuthProbe() {
  const { user, isAuthenticated, isAdmin } = useAuth();
  return <div>{isAuthenticated ? `${user?.username}:${isAdmin}` : "anonymous"}</div>;
}

function BootstrapButton() {
  const { bootstrapAdmin } = useAuth();
  return (
    <button type="button" onClick={() => bootstrapAdmin("owner", "owner@example.com", "secret123")}>
      bootstrap
    </button>
  );
}

describe("auth", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    delete api.defaults.headers.common.Authorization;
  });

  it("stores the bootstrapped administrator session", async () => {
    const user = { id: 1, username: "owner", email: "owner@example.com", role: "admin", status: "active" } as const;
    vi.spyOn(api, "post").mockResolvedValue({ data: { token: "abc", user } });
    vi.spyOn(api, "get").mockResolvedValue({ data: user });

    render(
      <Wrapper>
        <BootstrapButton />
        <AuthProbe />
      </Wrapper>
    );

    await userEvent.click(screen.getByRole("button", { name: "bootstrap" }));

    await waitFor(() => expect(screen.getByText("owner:true")).toBeInTheDocument());
    expect(localStorage.getItem("auth_token")).toBe("abc");
    expect(JSON.parse(localStorage.getItem("auth_user") ?? "{}")).toMatchObject({ username: "owner", role: "admin" });
  });

  it("shows the administrator creation form when setup is required", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: { setup_required: true } });

    renderLoginPage();

    expect(await screen.findByRole("heading", { name: "创建管理员账户" })).toBeInTheDocument();
    expect(screen.getByLabelText("用户名")).toBeInTheDocument();
    expect(screen.getByLabelText("邮箱 (选填)")).toBeInTheDocument();
    expect(screen.getByLabelText("确认密码")).toBeInTheDocument();
    expect(screen.queryByText("没有账户？")).not.toBeInTheDocument();
  });

  it("shows only login after setup is complete", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: { setup_required: false } });

    renderLoginPage();

    expect(await screen.findByRole("heading", { name: "管理员登录" })).toBeInTheDocument();
    expect(screen.getByLabelText("用户名或邮箱")).toBeRequired();
    expect(screen.queryByText("没有账户？")).not.toBeInTheDocument();
  });

  it("does not expose account creation when setup status cannot be checked", async () => {
    const get = vi.spyOn(api, "get")
      .mockRejectedValueOnce(new Error("network error"))
      .mockResolvedValueOnce({ data: { setup_required: false } });

    renderLoginPage();

    expect(await screen.findByText("无法检查系统初始化状态")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "创建管理员账户" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "重试" }));

    expect(await screen.findByRole("heading", { name: "管理员登录" })).toBeInTheDocument();
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("switches to login when another request completes setup first", async () => {
    vi.spyOn(api, "get").mockResolvedValue({ data: { setup_required: true } });
    vi.spyOn(api, "post").mockRejectedValue(Object.assign(new Error("系统已经完成初始化"), { status: 409 }));

    renderLoginPage();

    await screen.findByRole("heading", { name: "创建管理员账户" });
    await userEvent.type(screen.getByLabelText("用户名"), "owner");
    await userEvent.type(screen.getByLabelText("邮箱 (选填)"), "owner@example.com");
    await userEvent.type(screen.getByLabelText("密码"), "secret123");
    await userEvent.type(screen.getByLabelText("确认密码"), "secret123");
    await userEvent.click(screen.getByRole("button", { name: "创建管理员" }));

    expect(await screen.findByRole("heading", { name: "管理员登录" })).toBeInTheDocument();
  });
});
