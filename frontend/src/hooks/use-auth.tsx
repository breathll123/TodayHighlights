import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import api, { fetchMe, loginUser, registerUser } from "@/api/client";
import type { AuthUser } from "@/api/types";

interface AuthContextType {
  token: string | null;
  user: AuthUser | null;
  login: (login: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  isAdmin: boolean;
}

const AuthContext = createContext<AuthContextType>({
  token: null,
  user: null,
  login: async () => {},
  register: async () => {},
  logout: () => {},
  isAuthenticated: false,
  isAdmin: false,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(localStorage.getItem("auth_token") ?? localStorage.getItem("admin_token"));
  const [user, setUser] = useState<AuthUser | null>(() => {
    const raw = localStorage.getItem("auth_user");
    return raw ? JSON.parse(raw) : null;
  });

  useEffect(() => {
    if (token) {
      api.defaults.headers.common.Authorization = `Bearer ${token}`;
      fetchMe().then(setUser).catch(() => logout());
    } else {
      delete api.defaults.headers.common.Authorization;
    }
  }, [token]);

  const persist = (nextToken: string, nextUser: AuthUser) => {
    localStorage.setItem("auth_token", nextToken);
    localStorage.removeItem("admin_token");
    localStorage.setItem("auth_user", JSON.stringify(nextUser));
    api.defaults.headers.common.Authorization = `Bearer ${nextToken}`;
    setToken(nextToken);
    setUser(nextUser);
  };

  const login = async (loginValue: string, password: string) => {
    const res = await loginUser({ login: loginValue, password });
    persist(res.token, res.user);
  };

  const register = async (username: string, email: string, password: string) => {
    const res = await registerUser({ username, email, password });
    persist(res.token, res.user);
  };

  const logout = () => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("admin_token");
    localStorage.removeItem("auth_user");
    delete api.defaults.headers.common.Authorization;
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ token, user, login, register, logout, isAuthenticated: !!token && !!user, isAdmin: user?.role === "admin" }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
