import { getApp, getApps, initializeApp } from 'firebase/app';
import {
  ConfirmationResult,
  RecaptchaVerifier,
  getAuth,
  onAuthStateChanged,
  signInWithPhoneNumber,
  signOut,
} from 'firebase/auth';

const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export const firebasePhoneEnabled = Object.values(config).every(Boolean);
const auth = firebasePhoneEnabled
  ? getAuth(getApps().length ? getApp() : initializeApp(config))
  : null;
let verifier: RecaptchaVerifier | null = null;
let confirmation: ConfirmationResult | null = null;

function captchaHost(): HTMLElement {
  let host = document.getElementById('firebase-phone-captcha');
  if (!host) {
    host = document.createElement('div');
    host.id = 'firebase-phone-captcha';
    document.body.appendChild(host);
  }
  return host;
}

export function watchPhoneIdentity(listener: (signedIn: boolean) => void): () => void {
  return auth ? onAuthStateChanged(auth, user => listener(Boolean(user))) : () => {};
}

export async function sendPhoneCode(phone: string): Promise<void> {
  if (!auth) throw new Error('Phone sign-in is not configured.');
  if (!/^\+[1-9]\d{7,14}$/.test(phone)) throw new Error('Enter a valid phone number with country code.');
  if (!verifier) verifier = new RecaptchaVerifier(auth, captchaHost(), { size: 'invisible' });
  try {
    confirmation = await signInWithPhoneNumber(auth, phone, verifier);
  } catch (error) {
    verifier.clear();
    verifier = null;
    throw error;
  }
}

export async function confirmPhoneCode(code: string): Promise<string> {
  if (!confirmation) throw new Error('Request a new code first.');
  const result = await confirmation.confirm(code);
  confirmation = null;
  return result.user.getIdToken();
}

export async function currentIdentityToken(): Promise<string | null> {
  return auth?.currentUser ? auth.currentUser.getIdToken() : null;
}

export function currentIdentityUid(): string | null {
  return auth?.currentUser?.uid ?? null;
}

export async function signOutPhone(): Promise<void> {
  if (auth) await signOut(auth);
  confirmation = null;
}
