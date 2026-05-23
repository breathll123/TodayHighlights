import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import api from "@/api/client";

interface AuthContextType {
  token: string | null;
  login: (password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType>({
  token: null,
  login: async () => {},
  logout: () => {},
  isAuthenticated: false,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(localStorage.getItem("admin_token"));

  useEffect(() => {
    if (token) {
      api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    } else {
      delete api.defaults.headers.common["Authorization"];
    }
  }, [token]);

  const login = async (password: string) => {
    const res = await api.post("/api/admin/login", { password });
    const t = res.data.token;
    localStorage.setItem("admin_token", t);
    api.defaults.headers.common["Authorization"] = `Bearer ${t}`;
    setToken(t);
  };

  const logout = () => {
    localStorage.removeItem("admin_token");
    delete api.defaults.headers.common["Authorization"];
    setToken(null);
  };

  return (
    <AuthContext.Provider value={{ token, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
