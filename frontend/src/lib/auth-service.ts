import type { AuthUser } from "@/store/authStore";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type AuthMode = "mock" | "live";

export function getAuthMode(): AuthMode {
  const mode = process.env.NEXT_PUBLIC_AUTH_MODE?.toLowerCase();
  return mode === "live" ? "live" : "mock";
}

export type SignupPayload = {
  email: string;
  password: string;
  fullName?: string;
};

export type AuthResult = {
  token: string;
  user: AuthUser;
};

function mockToken(): string {
  return `mock.jwt.${Date.now()}`;
}

async function mockLogin(email: string): Promise<AuthResult> {
  await new Promise((r) => setTimeout(r, 150));
  return {
    token: mockToken(),
    user: {
      id: "mock-user-1",
      email,
      fullName: "Mock User",
      role: "user",
    },
  };
}

async function mockSignup(payload: SignupPayload): Promise<AuthResult> {
  await new Promise((r) => setTimeout(r, 150));
  return {
    token: mockToken(),
    user: {
      id: `mock-user-${Date.now()}`,
      email: payload.email,
      fullName: payload.fullName ?? "New User",
      role: "user",
    },
  };
}

async function liveLogin(email: string, password: string): Promise<AuthResult> {
  const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Login failed (${res.status})`);
  }
  return (await res.json()) as AuthResult;
}

async function liveSignup(payload: SignupPayload): Promise<AuthResult> {
  const res = await fetch(`${API_BASE_URL}/api/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Signup failed (${res.status})`);
  }
  return (await res.json()) as AuthResult;
}

/**
 * Login — mock mode uses synthetic JWT + user; live mode calls backend until Supabase is wired.
 */
export async function login(
  email: string,
  password: string,
): Promise<AuthResult> {
  if (getAuthMode() === "mock") {
    return mockLogin(email);
  }
  return liveLogin(email, password);
}

/**
 * Signup — same adapter pattern as login.
 */
export async function signup(payload: SignupPayload): Promise<AuthResult> {
  if (getAuthMode() === "mock") {
    return mockSignup(payload);
  }
  return liveSignup(payload);
}
