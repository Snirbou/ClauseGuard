import { create } from "zustand";

import {
  getAuthToken,
  getAuthUser,
  removeAuthToken,
  removeAuthUser,
  setAuthToken,
  setAuthUser,
} from "@/lib/auth-utils";

export type AuthUser = {
  id: string;
  email: string;
  fullName?: string;
  role?: string;
};

export type LoginPayload = {
  token: string;
  user: AuthUser;
};

type AuthState = {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isHydrated: boolean;
  bootstrapAuth: () => void;
  login: (payload: LoginPayload) => void;
  logout: () => void;
  /** Updates client store from Server Component props — does not mutate cookies. */
  hydrateFromServer: (user: AuthUser | null) => void;
  setUser: (user: AuthUser | null) => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isHydrated: false,
  bootstrapAuth: () => {
    const token = getAuthToken();
    const user = getAuthUser();
    set({
      user: token ? user : null,
      isAuthenticated: Boolean(token),
      isHydrated: true,
    });
  },
  login: ({ token, user }) => {
    setAuthToken(token);
    setAuthUser(user);
    set({ user, isAuthenticated: true, isHydrated: true });
  },
  logout: () => {
    removeAuthToken();
    removeAuthUser();
    set({ user: null, isAuthenticated: false, isHydrated: true });
  },
  hydrateFromServer: (user) => {
    const token = getAuthToken();
    set({
      user,
      isAuthenticated: Boolean(token),
      isHydrated: true,
    });
  },
  setUser: (user) => {
    if (user) {
      setAuthUser(user);
    } else {
      removeAuthUser();
    }
    set({ user, isAuthenticated: Boolean(user) });
  },
}));
