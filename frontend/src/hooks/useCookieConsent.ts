import { useEffect, useState } from 'react';

const STORAGE_KEY = 'cookie_consent_accepted';
const STORAGE_VALUE = '1';

export interface UseCookieConsentReturn {
  /** Пользователь принял cookie-уведомление. */
  isAccepted: boolean;
  /** Чтение из localStorage завершено. */
  isLoaded: boolean;
  /** Зафиксировать принятие cookie-уведомления. */
  accept: () => void;
}

export function useCookieConsent(): UseCookieConsentReturn {
  const [isAccepted, setIsAccepted] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      setIsAccepted(window.localStorage.getItem(STORAGE_KEY) === STORAGE_VALUE);
    } catch (error) {
      console.error('useCookieConsent: чтение localStorage не удалось', error);
    } finally {
      setIsLoaded(true);
    }
  }, []);

  const accept = () => {
    if (typeof window !== 'undefined') {
      try {
        window.localStorage.setItem(STORAGE_KEY, STORAGE_VALUE);
      } catch (error) {
        console.error('useCookieConsent: запись localStorage не удалась', error);
      }
    }

    setIsAccepted(true);
  };

  return { isAccepted, isLoaded, accept };
}
