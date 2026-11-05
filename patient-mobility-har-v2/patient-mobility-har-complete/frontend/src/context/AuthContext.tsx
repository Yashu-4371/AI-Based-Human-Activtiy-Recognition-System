import * as React from "react";
import * as authService from "@/services/authService";
import type { User } from "@/services/authService";

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = React.createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<User | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);

  React.useEffect(() => {
    const storedUser = localStorage.getItem("current_user");
    const storedToken = localStorage.getItem("access_token");
    if (storedUser && storedToken) {
      setUser(JSON.parse(storedUser));
    }
    setIsLoading(false);
  }, []);

  const login = React.useCallback(async (email: string, password: string) => {
    const response = await authService.login(email, password);
    localStorage.setItem("access_token", response.access_token);
    localStorage.setItem("current_user", JSON.stringify(response.user));
    setUser(response.user);
  }, []);

  const logout = React.useCallback(() => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("current_user");
    setUser(null);
  }, []);

  const value: AuthContextValue = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthContext() {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuthContext must be used within an AuthProvider");
  return ctx;
}
