import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { useNavigate } from "react-router-dom";


// ------------------------
// Types
// ------------------------
interface User {
  id: string;
  email: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<{ error: string | null }>;
  signup: (email: string, password: string) => Promise<{ error: string | null }>;
  logout: () => void;
}

// ------------------------
// Context
// ------------------------
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// ------------------------
// Provider
// ------------------------
export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const navigate = useNavigate();

  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem("access_token"));
  const [loading, setLoading] = useState(true);

  // Load user from localStorage on mount
  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    const storedToken = localStorage.getItem("access_token");

    if (storedUser && storedToken) {
      setUser(JSON.parse(storedUser));
      setToken(storedToken);
    }

    setLoading(false);
  }, []);

  // ------------------------
  // Login
  // ------------------------
  const login = async (email: string, password: string) => {
    try {
      const res = await fetch("http://localhost:8000/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (!res.ok) return { error: data.detail || "Login failed" };

      setToken(data.access_token);
      setUser(data.user);

      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("user", JSON.stringify(data.user));

      navigate("/incidents");
      return { error: null };
    } catch (error: any) {
      console.error("Login error:", error);
      return { error: "Login failed" };
    }
  };

  // ------------------------
  // Signup
  // ------------------------
  const signup = async (email: string, password: string) => {
    try {
      const res = await fetch("http://localhost:8000/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (!res.ok) return { error: data.detail || "Signup failed" };

      setToken(data.access_token);
      setUser(data.user);

      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("user", JSON.stringify(data.user));

      navigate("/incidents");
      return { error: null };
    } catch (error: any) {
      console.error("Signup error:", error);
      return { error: "Signup failed" };
    }
  };

  // ------------------------
  // Logout
  // ------------------------
  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    navigate("/login");
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

// ------------------------
// Hook to use Auth
// ------------------------
export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
};
