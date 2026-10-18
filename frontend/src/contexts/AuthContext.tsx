import { useQueryClient } from "@tanstack/react-query";
import { revokeAssistantSession, adoptAssistantSession, clearAssistantSession, initializeAssistant, assistantAuthHeaders } from "@/lib/assistantClient";
import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { useTheme } from 'next-themes';
import { confirmPhoneCode, currentIdentityUid, firebasePhoneEnabled, sendPhoneCode, signOutPhone, watchPhoneIdentity } from '@/lib/firebasePhoneAuth';

const API_URL = import.meta.env.VITE_API_URL || '';

export const DEMO_TEST_PHONE = '9999999999';

export const isDemoPhoneNumber = (phone: string): boolean => {
  const digits = String(phone || '').replace(/\D/g, '');
  return digits === '9999999999' || digits === '919999999999';
};

interface AuthContextType {
  isAuthenticated: boolean;
  authReady: boolean;
  hardwareConnected: boolean;
  connectHardware: (deviceId: string) => void;
  disconnectHardware: () => void;
  sendOtp: (phone: string, isSignup?: boolean) => Promise<{ success: boolean; message?: string; otp?: string; sms_sent?: boolean; demo_bypass?: boolean }>;
  login: (phone: string, otp: string) => Promise<boolean>;
  loginDemoUser: (phone?: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { readonly children: React.ReactNode }) {
  const { setTheme } = useTheme();
  const queryClient = useQueryClient();
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    return !firebasePhoneEnabled && localStorage.getItem('weather_auth') === 'true';
  });
  const [authReady, setAuthReady] = useState(!firebasePhoneEnabled);
  const loginInProgress = useRef(false);
  useEffect(() => {
    if (!firebasePhoneEnabled) return;
    let active = true;
    const unsubscribe = watchPhoneIdentity(signedIn => {
      if (!signedIn) {
        if (active) { setIsAuthenticated(false); setAuthReady(true); }
        return;
      }
      if (loginInProgress.current) return;
      void (async () => {
        try {
          const uid = currentIdentityUid();
          if (!uid) throw new Error('Missing phone identity');
          if (localStorage.getItem('firebase-session-uid') !== uid) clearAssistantSession();
          if (active) {
            localStorage.setItem('firebase-session-uid', uid);
            setIsAuthenticated(true);
            setAuthReady(true);
          }
          // Backend session renewal must not hold the signed-in UI hostage.
          await initializeAssistant();
          await assistantAuthHeaders();
        } catch {
          // Firebase remains authoritative; a temporary API outage is not logout.
          if (active && !currentIdentityUid()) setIsAuthenticated(false);
        } finally {
          if (active) setAuthReady(true);
        }
      })();
    });
    return () => { active = false; unsubscribe(); };
  }, []);
  const [hardwareConnected, setHardwareConnected] = useState(() => {
    return localStorage.getItem('hardware_connected') === 'true';
  });

  const connectHardware = useCallback((deviceId: string) => {
    setHardwareConnected(true);
    localStorage.setItem('hardware_connected', 'true');
    localStorage.setItem('hardware_device_id', deviceId);
  }, []);

  const disconnectHardware = useCallback(() => {
    setHardwareConnected(false);
    localStorage.removeItem('hardware_connected');
    localStorage.removeItem('hardware_device_id');
  }, []);

  const sendOtp = useCallback(async (phone: string, isSignup: boolean = false): Promise<{ success: boolean; message?: string; otp?: string; sms_sent?: boolean; demo_bypass?: boolean }> => {

    if (firebasePhoneEnabled) {
      try {
        await sendPhoneCode(phone);
        return { success: true, sms_sent: true };
      } catch (error) {
        return { success: false, message: error instanceof Error ? error.message : 'Could not send a sign-in code.' };
      }
    }

    try {
      const response = await fetch(`${API_URL}/api/auth/send-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, is_signup: isSignup }),
      });
      const data = await response.json();
      
      if (!response.ok) {
        return { success: false, message: data.detail || 'Failed to send OTP.' };
      }
      
      return { success: data.status === "success", otp: data.otp, sms_sent: Boolean(data.sms_sent), demo_bypass: Boolean(data.demo_bypass) };
    } catch {

      return { success: false, message: 'Network error. Please try again.' };
    }
  }, []);


  const login = useCallback(async (phone: string, otp: string): Promise<boolean> => {

    loginInProgress.current = true;
    try {
      const response = firebasePhoneEnabled
        ? await fetch(`${API_URL}/api/assistant/sessions`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${await confirmPhoneCode(otp)}` },
          })
        : await fetch(`${API_URL}/api/auth/verify-otp`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone, otp }),
          });
      const data = await response.json();
      
      if (response.ok && (firebasePhoneEnabled || data.status === "success") && data.token) {
        const sid = data.session_id ?? data.id ?? data.session?.id;
        if (!sid) {
          if (firebasePhoneEnabled) await signOutPhone();
          return false;
        }
        await queryClient.cancelQueries();
        queryClient.clear();
        await adoptAssistantSession(sid, data.token, { background: true });
        setIsAuthenticated(true);
        if (firebasePhoneEnabled) {
          const uid = currentIdentityUid();
          if (uid) localStorage.setItem('firebase-session-uid', uid);
          setAuthReady(true);
        }
        if (!firebasePhoneEnabled) localStorage.setItem('weather_auth', 'true');
        localStorage.setItem('user_phone', phone);
        setTheme('light');
        return true;
      }
      if (firebasePhoneEnabled) await signOutPhone();
      return false;
    } catch {
      if (firebasePhoneEnabled) await signOutPhone();
      return false;
    } finally {
      loginInProgress.current = false;
    }
  }, [setTheme, queryClient]);

  const loginDemoUser = useCallback(async (phone: string = DEMO_TEST_PHONE): Promise<boolean> => {
    if (firebasePhoneEnabled) return false;
    if (!isDemoPhoneNumber(phone)) return false;
    const issued = await sendOtp(phone);
    if (!issued.success || !issued.demo_bypass) return false;
    return login(phone, "999999");
  }, [sendOtp, login]);

  const logout = useCallback(async () => {
    setIsAuthenticated(false);
    setHardwareConnected(false);
    const revocation = revokeAssistantSession();
    await signOutPhone();
    await queryClient.cancelQueries();
    queryClient.clear();
    setIsAuthenticated(false);
    setHardwareConnected(false);
    localStorage.removeItem('weather_auth');
    localStorage.removeItem('user_phone');
    localStorage.removeItem('firebase-session-uid');
    localStorage.removeItem('hardware_connected');
    localStorage.removeItem('hardware_device_id');
    await revocation;
  }, [queryClient]);

  return (
    <AuthContext.Provider value={{ isAuthenticated, authReady, hardwareConnected, connectHardware, disconnectHardware, sendOtp, login, loginDemoUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
