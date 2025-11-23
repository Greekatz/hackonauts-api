// API utility with graceful fallback to demo data

const API_BASE = 'http://localhost:8000'; // your FastAPI URL

interface LoginResponse {
  access_token: string;
  user: { id: string; email: string };
}

interface LoginFallback {
  access_token: string;
  user: { id: string; email: string };
}

export async function loginApi(
  email: string,
  password: string,
  fallback?: LoginFallback
): Promise<LoginResponse> {
  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      console.warn('Login failed, using fallback');
      if (fallback) return fallback;
      throw new Error('Login failed');
    }

    return await res.json();
  } catch (error) {
    console.warn('Login API error', error);
    if (fallback) return fallback;
    throw error;
  }
}


export async function fetchWithFallback<T>(
  endpoint: string,
  fallbackData: T,
  options?: RequestInit
): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      console.warn(`API call failed: ${endpoint}, using fallback data`);
      return fallbackData;
    }

    return await response.json();
  } catch (error) {
    console.warn(`API call error: ${endpoint}, using fallback data`, error);
    return fallbackData;
  }
}

export async function postWithFallback<T>(
  endpoint: string,
  data: any,
  fallbackResponse: T
): Promise<T> {
  return fetchWithFallback(
    endpoint,
    fallbackResponse,
    {
      method: 'POST',
      body: JSON.stringify(data),
    }
  );
}
