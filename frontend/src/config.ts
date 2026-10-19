// Backend configuration for local development and live Vercel deployments

export const getStoredBackendUrl = (): string => {
  return localStorage.getItem('yolo_backend_url') || import.meta.env.VITE_BACKEND_URL || '';
};

export const setStoredBackendUrl = (url: string): void => {
  const cleanUrl = url.trim().replace(/\/+$/, '');
  if (cleanUrl) {
    localStorage.setItem('yolo_backend_url', cleanUrl);
  } else {
    localStorage.removeItem('yolo_backend_url');
  }
};

export const getApiUrl = (path: string): string => {
  const base = getStoredBackendUrl();
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return base ? `${base}${cleanPath}` : cleanPath;
};

export const getWsUrl = (path: string): string => {
  const base = getStoredBackendUrl();
  const cleanPath = path.startsWith('/') ? path : `/${path}`;

  if (base) {
    // If user provided http(s) URL, convert to ws(s)
    try {
      const parsed = new URL(base);
      const wsProtocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${wsProtocol}//${parsed.host}${cleanPath}`;
    } catch {
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${wsProtocol}//${base.replace(/^https?:\/\//, '')}${cleanPath}`;
    }
  }

  // Fallback to relative origin
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${cleanPath}`;
};
