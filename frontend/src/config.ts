// Backend configuration for local development and live Vercel deployments

export const sanitizeUrl = (input: string): string => {
  if (!input) return '';
  // Extract URL if the user accidentally copied text like "your url is: https://xyz.loca.lt"
  const urlMatch = input.match(/https?:\/\/[^\s"'<>]+/i);
  if (urlMatch) {
    return urlMatch[0].replace(/\/+$/, '');
  }

  const trimmed = input.trim().replace(/^['"]+|['"]+$/g, '').replace(/\/+$/, '');
  if (!trimmed) return '';

  // Auto-prepend http:// if entered as localhost:8000 or IP:port
  if (/^(localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?/i.test(trimmed)) {
    return `http://${trimmed}`;
  }

  return trimmed;
};

export const getStoredBackendUrl = (): string => {
  const raw = localStorage.getItem('yolo_backend_url') || import.meta.env.VITE_BACKEND_URL || '';
  return sanitizeUrl(raw);
};

export const setStoredBackendUrl = (url: string): void => {
  const cleanUrl = sanitizeUrl(url);
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
    try {
      const parsed = new URL(base);
      const wsProtocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${wsProtocol}//${parsed.host}${cleanPath}`;
    } catch {
      // If parsing fails, fall back to relative
    }
  }

  // Fallback to current browser host
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${cleanPath}`;
};
