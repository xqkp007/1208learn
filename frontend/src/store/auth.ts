import { create } from 'zustand';

export interface AuthUser {
  userId: number;
  username: string;
  fullName?: string | null;
  role: string;
  scenarioId: number;
}

interface AuthState {
  accessToken: string | null;
  user: AuthUser | null;
  setAuth: (token: string, user: AuthUser) => void;
  clearAuth: () => void;
}

const STORAGE_KEY = 'kb_review_auth';

function loadInitialState(): Pick<AuthState, 'accessToken' | 'user'> {
  if (typeof window === 'undefined') {
    return { accessToken: null, user: null };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { accessToken: null, user: null };
    const parsed = JSON.parse(raw) as { accessToken: string; user: AuthUser };
    return {
      accessToken: parsed.accessToken ?? null,
      user: parsed.user ?? null,
    };
  } catch {
    return { accessToken: null, user: null };
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: loadInitialState().accessToken,
  user: loadInitialState().user,
  setAuth: (token, user) => {
    set({ accessToken: token, user });
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ accessToken: token, user }),
      );
    } catch {
      // ignore
    }
  },
  clearAuth: () => {
    set({ accessToken: null, user: null });
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  },
}));

