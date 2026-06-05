import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/api/client";
import { AuthProvider, useAuth } from "@/hooks/use-auth";
import { LoginPage } from "@/pages/LoginPage";

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      <AuthProvider>
        <BrowserRouter>{children}</BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

function AuthProbe() {
  const { user, isAuthenticated, isAdmin } = useAuth();
  return <div>{isAuthenticated ? `${user?.username}:${isAdmin}` : "anonymous"}</div>;
}

describe("auth", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("stores logged in user role", async () => {
    vi.spyOn(api, "post").mockResolvedValue({
      data: { token: "abc", user: { id: 1, username: "admin", email: "", role: "admin", status: "active" } },
    });

    render(
      <Wrapper>
        <LoginPage />
        <AuthProbe />
      </Wrapper>
    );

    await userEvent.type(screen.getByLabelText("密码"), "secret123");
    await userEvent.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => expect(screen.getByText("admin:true")).toBeInTheDocument());
  });
});
