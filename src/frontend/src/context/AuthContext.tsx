import React, { createContext, useContext, useState, useEffect } from 'react';

export interface InvestigatorSession {
  badgeId: string;
  name: string;
  role: string;
  clearanceLevel: string;
  caseWorkspace: string;
  station: string;
  authenticatedAt: string;
}

interface AuthContextType {
  session: InvestigatorSession | null;
  isAuthenticated: boolean;
  loginDemo: (badgeId?: string, name?: string) => void;
  logout: () => void;
}

const STORAGE_KEY = 'sih26189_investigator_session';

const DEFAULT_DEMO_SESSION: InvestigatorSession = {
  badgeId: 'DEMO-USER',
  name: 'Demo Investigator',
  role: 'Investigation Workspace User',
  clearanceLevel: 'DEMO ACCESS',
  caseWorkspace: 'OPERATION HAWKEYE [CASE-2026-0814]',
  station: 'Local Demonstration Workspace',
  authenticatedAt: new Date().toISOString(),
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [session, setSession] = useState<InvestigatorSession | null>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        return JSON.parse(stored) as InvestigatorSession;
      }
    } catch {
      // ignore JSON parse error
    }
    return null;
  });

  useEffect(() => {
    if (session) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [session]);

  const loginDemo = (badgeId?: string, name?: string) => {
    const newSession: InvestigatorSession = {
      ...DEFAULT_DEMO_SESSION,
      badgeId: badgeId?.trim() || DEFAULT_DEMO_SESSION.badgeId,
      name: name?.trim() || DEFAULT_DEMO_SESSION.name,
      authenticatedAt: new Date().toISOString(),
    };
    setSession(newSession);
  };

  const logout = () => {
    setSession(null);
  };

  return (
    <AuthContext.Provider
      value={{
        session,
        isAuthenticated: !!session,
        loginDemo,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
