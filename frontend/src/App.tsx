import React, { useState, useEffect, useRef } from 'react';
import { 
  Activity, Shield, Play, Pause, RefreshCw, Layers, Cpu, 
  Database, Upload, Camera, Sliders, Grid, Radio, Check, Server, X
} from 'lucide-react';
import axios from 'axios';
import { getApiUrl, getWsUrl, getStoredBackendUrl, setStoredBackendUrl } from './config';
import './App.css';

interface ClassItem {
  id: number;
  name: string;
}

interface LogEntry {
  time: string;
  event: string;
  type: 'entry' | 'exit';
  id: number;
}

const App = () => {
  const [activeTab, setActiveTab] = useState<'stream' | 'analytics' | 'settings'>('stream');
  const [activeSource, setActiveSource] = useState<string>('mock');
  const [activeTracker, setActiveTracker] = useState<string>('bytetrack');
  const [activeModel, setActiveModel] = useState<string>('yolov8n');
  
  // Settings Sliders
  const [confThreshold, setConfThreshold] = useState<number>(0.25);
  const [iouThreshold, setIouThreshold] = useState<number>(0.45);
  
  // View Settings
  const [showBoxes, setShowBoxes] = useState<boolean>(true);
  const [showLabels, setShowLabels] = useState<boolean>(true);
  const [showScores, setShowScores] = useState<boolean>(true);
  const [showTrails, setShowTrails] = useState<boolean>(true);
  
  // Class Filters
  const [classesList, setClassesList] = useState<ClassItem[]>([]);
  const [activeClasses, setActiveClasses] = useState<number[]>([]);
  const [classSearch, setClassSearch] = useState<string>('');

  // RTSP URL
  const [rtspUrl, setRtspUrl] = useState<string>('');
  
  // File Upload State
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Live Telemetry
  const [stats, setStats] = useState({
    fps: 0,
    count: 0,
    total_unique: 0,
    model: 'yolov8n',
    tracker: 'bytetrack',
    classes: {} as Record<string, number>,
    logs: [] as LogEntry[]
  });
  
  const [historicalCounts, setHistoricalCounts] = useState<number[]>(new Array(25).fill(0));
  const [isStreaming, setIsStreaming] = useState<boolean>(true);
  const [systemConnected, setSystemConnected] = useState<boolean>(false);
  
  // Backend URL configuration (for Vercel & remote deployment)
  const [backendUrl, setBackendUrl] = useState<string>(getStoredBackendUrl());
  const [backendInput, setBackendInput] = useState<string>(getStoredBackendUrl());
  const [showBackendModal, setShowBackendModal] = useState<boolean>(false);

  const handleSaveBackendUrl = (urlToSave: string) => {
    setStoredBackendUrl(urlToSave);
    setBackendUrl(urlToSave.trim().replace(/\/+$/, ''));
    setShowBackendModal(false);
  };
  
  // Web Browser Webcam Stream Reference
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamImgRef = useRef<HTMLImageElement>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const browserWsRef = useRef<WebSocket | null>(null);
  const animationFrameIdRef = useRef<number | null>(null);

  // Load available settings & classes from backend on mount
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await axios.get(getApiUrl('/settings'));
        const data = response.data;
        setActiveModel(data.model);
        setActiveTracker(data.tracker);
        setConfThreshold(data.conf_threshold);
        setIouThreshold(data.iou_threshold);
        setActiveClasses(data.active_classes || []);
        setShowBoxes(data.show_boxes);
        setShowLabels(data.show_labels);
        setShowScores(data.show_scores);
        setShowTrails(data.show_trails);
        setActiveSource(data.source_type);
        setClassesList(data.available_classes || []);
        setSystemConnected(true);
      } catch (err) {
        console.error("Failed to connect to backend:", err);
        setSystemConnected(false);
      }
    };
    
    fetchSettings();
    const interval = setInterval(fetchSettings, 5000); // Poll server connection
    return () => clearInterval(interval);
  }, [backendUrl]);

  // Sync settings modifications to the backend
  const syncSettings = async (updates: Record<string, any>) => {
    try {
      const response = await axios.post(getApiUrl('/settings'), updates);
      setSystemConnected(true);
      return response.data;
    } catch (err) {
      console.error("Failed to sync settings:", err);
      setSystemConnected(false);
    }
  };

  // Telemetry WebSocket Listener
  useEffect(() => {
    let ws: WebSocket;
    
    const connectTelemetry = () => {
      ws = new WebSocket(getWsUrl('/ws'));
      
      ws.onopen = () => {
        console.log("Telemetry WebSocket connected.");
        setSystemConnected(true);
      };
      
      ws.onmessage = (event) => {
        try {
          const telemetryData = JSON.parse(event.data);
          setStats(telemetryData);
          setHistoricalCounts(prev => {
            const next = [...prev.slice(1), telemetryData.count];
            return next;
          });
        } catch (e) {
          console.error("Error parsing telemetry WebSocket data:", e);
        }
      };
      
      ws.onclose = () => {
        console.log("Telemetry WebSocket disconnected. Reconnecting...");
        setTimeout(connectTelemetry, 3000);
      };
      
      ws.onerror = (err) => {
        console.error("Telemetry WebSocket error:", err);
        ws.close();
      };
    };
    
    connectTelemetry();
    return () => {
      if (ws) ws.close();
    };
  }, [backendUrl]);

  // Manage Web Browser Webcam Capturing and Streaming over WebSocket
  useEffect(() => {
    if (activeSource === 'browser' && isStreaming) {
      startBrowserStream();
    } else {
      stopBrowserStream();
    }
    
    return () => {
      stopBrowserStream();
    };
  }, [activeSource, isStreaming]);

  const startBrowserStream = async () => {
    try {
      // Connect WebSocket for streaming
      const ws = new WebSocket(getWsUrl('/ws/browser_stream'));
      browserWsRef.current = ws;
      
      ws.onopen = async () => {
        console.log("Browser Webcam Stream WebSocket opened.");
        
        // Grab browser webcam stream
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 640, height: 480, frameRate: { ideal: 30 } }
        });
        
        localStreamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play();
        }
        
        // Start sending loops
        captureAndSendLoop();
      };

      ws.onmessage = (event) => {
        // Render processed image returned by server
        const blob = event.data;
        if (streamImgRef.current && blob instanceof Blob) {
          const url = URL.createObjectURL(blob);
          const oldUrl = streamImgRef.current.src;
          streamImgRef.current.src = url;
          if (oldUrl.startsWith('blob:')) {
            URL.revokeObjectURL(oldUrl);
          }
        }
      };

      ws.onclose = () => {
        console.log("Browser Webcam Stream WebSocket closed.");
        stopBrowserStream();
      };
    } catch (err) {
      console.error("Error starting browser webcam stream:", err);
      alert("Could not access camera. Please check camera permissions.");
      handleSourceChange('mock');
    }
  };

  const captureAndSendLoop = () => {
    if (!browserWsRef.current || browserWsRef.current.readyState !== WebSocket.OPEN) return;
    
    const video = videoRef.current;
    const canvas = canvasRef.current;
    
    if (video && canvas && video.readyState === video.HAVE_ENOUGH_DATA) {
      const ctx = canvas.getContext('2d');
      if (ctx) {
        // Draw video frame onto hidden canvas
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // Export to JPEG Blob and send
        canvas.toBlob((blob) => {
          if (blob && browserWsRef.current && browserWsRef.current.readyState === WebSocket.OPEN) {
            browserWsRef.current.send(blob);
          }
        }, 'image/jpeg', 0.7);
      }
    }
    
    // Schedule next frame
    animationFrameIdRef.current = requestAnimationFrame(captureAndSendLoop);
  };

  const stopBrowserStream = () => {
    if (animationFrameIdRef.current) {
      cancelAnimationFrame(animationFrameIdRef.current);
      animationFrameIdRef.current = null;
    }
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach(track => track.stop());
      localStreamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    if (browserWsRef.current) {
      browserWsRef.current.close();
      browserWsRef.current = null;
    }
  };

  // Switch Stream Sources
  const handleSourceChange = async (source: string, details?: string) => {
    setActiveSource(source);
    await syncSettings({
      source_type: source,
      source_details: details
    });
  };

  // Switch YOLO models
  const handleModelChange = async (model: string) => {
    setActiveModel(model);
    await syncSettings({ model });
  };

  // Switch Tracking algorithms
  const handleTrackerChange = async (tracker: string) => {
    setActiveTracker(tracker);
    await syncSettings({ tracker });
  };

  // Switch class filtering
  const handleClassToggle = async (classId: number) => {
    let nextClasses = [...activeClasses];
    if (nextClasses.includes(classId)) {
      nextClasses = nextClasses.filter(id => id !== classId);
    } else {
      nextClasses.push(classId);
    }
    setActiveClasses(nextClasses);
    await syncSettings({ active_classes: nextClasses });
  };

  const clearAllClasses = async () => {
    setActiveClasses([]);
    await syncSettings({ active_classes: [] });
  };

  const selectAllClasses = async () => {
    // Select popular categories: Person, Bicycle, Car, Motorcycle, Dog, Cat (IDs: 0, 1, 2, 3, 16, 15)
    const popular = [0, 1, 2, 3, 15, 16];
    setActiveClasses(popular);
    await syncSettings({ active_classes: popular });
  };

  // Video File Upload Handler
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    const file = files[0];
    setIsUploading(true);
    setUploadProgress("Uploading file...");
    
    const formData = new FormData();
    formData.append("file", file);
    
    try {
      await axios.post(getApiUrl("/upload_video"), formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      
      setUploadProgress("File ready!");
      setActiveSource("file");
      setIsUploading(false);
      setTimeout(() => setUploadProgress(""), 2000);
    } catch (err) {
      console.error("Error uploading file:", err);
      setUploadProgress("Upload failed.");
      setIsUploading(false);
    }
  };

  // RTSP Connect Stream
  const handleRtspConnect = async () => {
    if (!rtspUrl) return;
    handleSourceChange("url", rtspUrl);
  };

  // SVG Chart calculation parameters
  const getLinePath = () => {
    const width = 500;
    const height = 180;
    const maxVal = Math.max(...historicalCounts, 5);
    const points = historicalCounts.map((val, idx) => {
      const x = (idx / (historicalCounts.length - 1)) * width;
      const y = height - (val / maxVal) * (height - 20) - 10;
      return `${x},${y}`;
    });
    return `M ${points.join(' L ')}`;
  };

  const getAreaPath = () => {
    const width = 500;
    const height = 180;
    const maxVal = Math.max(...historicalCounts, 5);
    const points = historicalCounts.map((val, idx) => {
      const x = (idx / (historicalCounts.length - 1)) * width;
      const y = height - (val / maxVal) * (height - 20) - 10;
      return `${x},${y}`;
    });
    return `M 0,${height} L ${points.join(' L ')} L ${width},${height} Z`;
  };

  const filteredClasses = classesList.filter(c => 
    c.name.toLowerCase().includes(classSearch.toLowerCase())
  );

  return (
    <div className="dashboard-container">
      {/* Sidebar navigation & Controls */}
      <aside className="sidebar glass-panel">
        <div className="logo">
          <Shield className="accent-icon" size={28} />
          <span>CORTEX ENGINE</span>
        </div>
        
        <nav className="nav-menu">
          <div 
            className={`nav-item ${activeTab === 'stream' ? 'active' : ''}`}
            onClick={() => setActiveTab('stream')}
          >
            <Activity size={20} />
            <span>Telemetry Feed</span>
          </div>
          <div 
            className={`nav-item ${activeTab === 'analytics' ? 'active' : ''}`}
            onClick={() => setActiveTab('analytics')}
          >
            <Database size={20} />
            <span>Session Analytics</span>
          </div>
          <div 
            className={`nav-item ${activeTab === 'settings' ? 'active' : ''}`}
            onClick={() => setActiveTab('settings')}
          >
            <Sliders size={20} />
            <span>System Config</span>
          </div>
        </nav>

        <div className="sidebar-divider"></div>

        {/* Global configuration selectors inside Sidebar */}
        <div className="sidebar-controls">
          <div className="control-header">TRACKING ALGORITHM</div>
          <div className="control-item">
            <select 
              className="custom-select"
              value={activeTracker} 
              onChange={(e) => handleTrackerChange(e.target.value)}
            >
              <option value="bytetrack">ByteTrack (YOLOv8 Native)</option>
              <option value="botsort">BotSORT (YOLOv8 Native)</option>
              <option value="deepsort">DeepSORT (Custom Engine)</option>
            </select>
          </div>

          <div className="control-header" style={{ marginTop: '10px' }}>DETECTION MODEL</div>
          <div className="control-item">
            <select 
              className="custom-select"
              value={activeModel} 
              onChange={(e) => handleModelChange(e.target.value)}
            >
              <option value="yolov8n">YOLOv8 Nano (High FPS)</option>
              <option value="yolov8s">YOLOv8 Small (Balanced)</option>
              <option value="yolov8m">YOLOv8 Medium (High Accuracy)</option>
            </select>
          </div>
        </div>

        {/* System Health stats inside Sidebar */}
        <div className="system-health">
          <div className="health-item">
            <span>Server Response</span>
            <span className="health-value text-emerald">Active</span>
          </div>
          <div className="health-bar-bg">
            <div className="health-bar-fill" style={{ width: '100%', background: 'var(--accent-color)' }}></div>
          </div>
          <div className="health-item" style={{ marginTop: '6px' }}>
            <span>Inference Speed</span>
            <span className="health-value">
              {stats.fps > 0 ? `${Math.round(1000 / stats.fps)} ms` : '--'}
            </span>
          </div>
        </div>

        <div className="sidebar-divider"></div>

        {/* Creator Info */}
        <div className="creator-info">
          <div className="creator-label">DEVELOPER</div>
          <div className="creator-name">Gollavilli Shanmukh Vardhan Sai</div>
          <a href="mailto:shannuvardhan802@gmail.com" className="creator-email">
            shannuvardhan802@gmail.com
          </a>
        </div>
      </aside>

      {/* Main Panel Content */}
      <main className="main-content">
        <header className="main-header">
          <div className="header-title-sec">
            <h2>Live Multi-Object Tracking Dashboard</h2>
            <p>Powered by Ultralytics YOLOv8 & Real-time Association Filters</p>
          </div>
          
          <div className="header-actions">
            <button 
              className="server-config-btn"
              onClick={() => setShowBackendModal(true)}
              title="Configure Backend Server Endpoint"
            >
              <Server size={14} />
              <span>{backendUrl ? (backendUrl.length > 22 ? backendUrl.slice(0, 22) + '...' : backendUrl) : 'Connect Backend'}</span>
            </button>

            <div className={`status-badge ${systemConnected ? '' : 'offline'}`}>
              <div className="pulse-dot"></div>
              <span>System: {systemConnected ? 'Online' : 'Offline'}</span>
            </div>
          </div>
        </header>

        {activeTab === 'stream' && (
          <div className="grid-layout">
            
            {/* Live Feed Video Panel */}
            <section className="feed-section glass-panel">
              <div className="panel-header">
                <h3>Primary Stream Feed</h3>
                <div className="panel-controls">
                  
                  {/* Select sources buttons */}
                  <button 
                    className={`btn-icon ${activeSource === 'mock' ? 'active' : ''}`}
                    title="Mock Generator"
                    onClick={() => handleSourceChange('mock')}
                  >
                    <Grid size={18} />
                  </button>

                  <button 
                    className={`btn-icon ${activeSource === 'webcam' ? 'active' : ''}`}
                    title="Host PC Webcam"
                    onClick={() => handleSourceChange('webcam')}
                  >
                    <Camera size={18} />
                  </button>

                  <button 
                    className={`btn-icon ${activeSource === 'browser' ? 'active' : ''}`}
                    title="Browser Webcam"
                    onClick={() => handleSourceChange('browser')}
                  >
                    <Radio size={18} />
                  </button>

                  <button 
                    className={`btn-icon ${activeSource === 'file' ? 'active' : ''}`}
                    title="Upload File"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Upload size={18} />
                  </button>

                  <input 
                    type="file" 
                    ref={fileInputRef} 
                    className="hidden-file-input" 
                    accept="video/*" 
                    onChange={handleFileUpload} 
                  />

                  <div style={{ width: '1px', height: '20px', background: 'var(--panel-border)' }}></div>

                  {/* Play Pause button */}
                  <button 
                    className="btn-icon" 
                    onClick={() => setIsStreaming(!isStreaming)}
                  >
                    {isStreaming ? <Pause size={18} /> : <Play size={18} />}
                  </button>
                </div>
              </div>

              {/* Feed video viewport */}
              <div className="video-container">
                {isStreaming ? (
                  activeSource === 'browser' ? (
                    <>
                      {/* Hidden canvas & video elements for capturing browser camera */}
                      <video ref={videoRef} style={{ display: 'none' }} width="640" height="480" playsInline></video>
                      <canvas ref={canvasRef} style={{ display: 'none' }} width="640" height="480"></canvas>
                      <img ref={streamImgRef} alt="Web Client Webcam Stream" />
                    </>
                  ) : (
                    <img 
                      src={`${getApiUrl('/video_feed')}?t=${Date.now()}`} 
                      alt="Object Tracking Stream" 
                      onError={() => {
                        // Switch to mock if stream URL errors
                        console.error("Stream connection failed.");
                      }}
                    />
                  )
                ) : (
                  <div className="stream-paused">
                    <Pause size={48} className="accent-icon" />
                    <span className="paused-text">Stream Feed Paused</span>
                  </div>
                )}

                {/* Upload indicators overlay */}
                {isUploading && (
                  <div className="toast-msg">
                    <RefreshCw className="pulse-dot" size={16} style={{ display: 'inline', marginRight: '8px' }} />
                    {uploadProgress}
                  </div>
                )}
              </div>
            </section>

            {/* Statistics Telemetry bar */}
            <section className="stats-section">
              <div className="stat-card glass-panel blue">
                <span className="stat-label">Frame Refresh Speed</span>
                <div className="stat-value-row">
                  <span className="stat-value glow-text">{stats.fps} FPS</span>
                  <Cpu size={24} className="accent-icon" />
                </div>
              </div>

              <div className="stat-card glass-panel purple">
                <span className="stat-label">Active Objects In Frame</span>
                <div className="stat-value-row">
                  <span className="stat-value glow-text-purple">{stats.count}</span>
                  <Layers size={24} style={{ color: 'var(--accent-purple)' }} />
                </div>
              </div>

              <div className="stat-card glass-panel emerald">
                <span className="stat-label">Total Unique Detections</span>
                <div className="stat-value-row">
                  <span className="stat-value glow-text-emerald">{stats.total_unique}</span>
                  <Database size={24} style={{ color: 'var(--accent-emerald)' }} />
                </div>
              </div>

              {/* Event Logs terminal widget */}
              <div className="event-log-container glass-panel">
                <div className="event-log-title">Activity event console</div>
                <div className="event-log">
                  {stats.logs && stats.logs.length > 0 ? (
                    stats.logs.map((log, idx) => (
                      <div key={idx} className={`log-entry ${log.type}`}>
                        <span className="log-time">[{log.time}]</span>
                        <span>{log.event}</span>
                      </div>
                    ))
                  ) : (
                    <div className="log-entry" style={{ color: 'var(--text-muted)' }}>
                      [System Initialize] Waiting for detections...
                    </div>
                  )}
                </div>
              </div>
            </section>
          </div>
        )}

        {/* Analytics Tab View */}
        {activeTab === 'analytics' && (
          <div className="analytics-view">
            <div className="analytics-grid">
              <div className="stat-card glass-panel blue">
                <span className="stat-label">Session FPS average</span>
                <span className="stat-value glow-text" style={{ marginTop: '12px' }}>{stats.fps} FPS</span>
              </div>
              <div className="stat-card glass-panel purple">
                <span className="stat-label">Current Object Count</span>
                <span className="stat-value glow-text-purple" style={{ marginTop: '12px' }}>{stats.count}</span>
              </div>
              <div className="stat-card glass-panel emerald">
                <span className="stat-label">Unique Tracker IDs</span>
                <span className="stat-value glow-text-emerald" style={{ marginTop: '12px' }}>{stats.total_unique}</span>
              </div>
              <div className="stat-card glass-panel">
                <span className="stat-label">Association Filter</span>
                <span className="stat-value" style={{ marginTop: '12px', fontSize: '1.5rem', textTransform: 'uppercase' }}>
                  {stats.tracker}
                </span>
              </div>
            </div>

            {/* SVG Charts Row */}
            <div className="analytics-chart-row">
              <div className="chart-panel glass-panel">
                <div className="chart-panel-header">
                  <h3>Historical Objects Tracked (Last 25 Frames)</h3>
                  <Activity size={18} className="accent-icon" />
                </div>
                
                {/* SVG Line Chart */}
                <div className="chart-body">
                  <svg className="svg-chart" viewBox="0 0 500 180" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="chart-gradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--accent-color)" stopOpacity="0.4" />
                        <stop offset="100%" stopColor="var(--accent-color)" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>
                    
                    {/* Horizontal Grid lines */}
                    <line x1="0" y1="30" x2="500" y2="30" className="chart-grid-line" />
                    <line x1="0" y1="75" x2="500" y2="75" className="chart-grid-line" />
                    <line x1="0" y1="120" x2="500" y2="120" className="chart-grid-line" />
                    <line x1="0" y1="165" x2="500" y2="165" className="chart-grid-line" />
                    
                    {/* Area under line */}
                    <path d={getAreaPath()} className="chart-fill-path" />
                    
                    {/* The Line path */}
                    <path d={getLinePath()} className="chart-path" />
                  </svg>
                </div>
              </div>

              {/* Class distribution progress bars */}
              <div className="chart-panel glass-panel">
                <div className="chart-panel-header">
                  <h3>Active Categories</h3>
                  <Grid size={18} style={{ color: 'var(--accent-purple)' }} />
                </div>
                <div className="distribution-list">
                  {Object.keys(stats.classes).length > 0 ? (
                    Object.entries(stats.classes).map(([className, count], idx) => {
                      const total = Object.values(stats.classes).reduce((a, b) => a + b, 0);
                      const pct = total > 0 ? (count / total) * 100 : 0;
                      return (
                        <div key={idx} className="dist-item">
                          <div className="dist-meta">
                            <span className="dist-label">{className}</span>
                            <span className="dist-val">{count} ({Math.round(pct)}%)</span>
                          </div>
                          <div className="dist-bar-bg">
                            <div className="dist-bar-fill" style={{ width: `${pct}%` }}></div>
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', marginTop: '40px' }}>
                      No active objects tracked.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* System Settings Tab View */}
        {activeTab === 'settings' && (
          <div className="settings-view">
            
            {/* Visual parameters configuration */}
            <div className="settings-group-panel glass-panel">
              <h3>Detection & Tracking Thresholds</h3>
              <div className="settings-grid">
                <div className="slider-group">
                  <div className="slider-header">
                    <span>Confidence Limit</span>
                    <span className="slider-value">{confThreshold.toFixed(2)}</span>
                  </div>
                  <input 
                    type="range" 
                    min="0.1" 
                    max="0.9" 
                    step="0.05"
                    value={confThreshold}
                    className="range-input"
                    onChange={(e) => {
                      const val = parseFloat(e.target.value);
                      setConfThreshold(val);
                      syncSettings({ conf_threshold: val });
                    }}
                  />
                </div>

                <div className="slider-group">
                  <div className="slider-header">
                    <span>Intersection over Union (IoU) Limit</span>
                    <span className="slider-value">{iouThreshold.toFixed(2)}</span>
                  </div>
                  <input 
                    type="range" 
                    min="0.1" 
                    max="0.9" 
                    step="0.05"
                    value={iouThreshold}
                    className="range-input"
                    onChange={(e) => {
                      const val = parseFloat(e.target.value);
                      setIouThreshold(val);
                      syncSettings({ iou_threshold: val });
                    }}
                  />
                </div>

                <div className="sidebar-divider"></div>

                <div className="toggle-group">
                  <div className="toggle-label-sec">
                    <span>Bounding Boxes</span>
                    <span>Draw boundaries on active targets</span>
                  </div>
                  <label className="switch">
                    <input 
                      type="checkbox" 
                      checked={showBoxes} 
                      onChange={(e) => {
                        const val = e.target.checked;
                        setShowBoxes(val);
                        syncSettings({ show_boxes: val });
                      }}
                    />
                    <span className="slider"></span>
                  </label>
                </div>

                <div className="toggle-group">
                  <div className="toggle-label-sec">
                    <span>Display Labels</span>
                    <span>Overlay tracking ID and class name</span>
                  </div>
                  <label className="switch">
                    <input 
                      type="checkbox" 
                      checked={showLabels} 
                      onChange={(e) => {
                        const val = e.target.checked;
                        setShowLabels(val);
                        syncSettings({ show_labels: val });
                      }}
                    />
                    <span className="slider"></span>
                  </label>
                </div>

                <div className="toggle-group">
                  <div className="toggle-label-sec">
                    <span>Display Scores</span>
                    <span>Overlay detection confidence metrics</span>
                  </div>
                  <label className="switch">
                    <input 
                      type="checkbox" 
                      checked={showScores} 
                      disabled={!showLabels}
                      onChange={(e) => {
                        const val = e.target.checked;
                        setShowScores(val);
                        syncSettings({ show_scores: val });
                      }}
                    />
                    <span className="slider"></span>
                  </label>
                </div>

                <div className="toggle-group">
                  <div className="toggle-label-sec">
                    <span>Draw Target Trails</span>
                    <span>Render motion history paths</span>
                  </div>
                  <label className="switch">
                    <input 
                      type="checkbox" 
                      checked={showTrails} 
                      onChange={(e) => {
                        const val = e.target.checked;
                        setShowTrails(val);
                        syncSettings({ show_trails: val });
                      }}
                    />
                    <span className="slider"></span>
                  </label>
                </div>
              </div>
            </div>

            {/* Class filter category selections */}
            <div className="settings-group-panel glass-panel">
              <h3>Class Category Filtering</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '14px' }}>
                Restrict detection and tracking outputs to specific object classes. If none are selected, all categories are tracked.
              </p>

              <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                <input 
                  type="text"
                  placeholder="Filter category names..."
                  className="custom-select"
                  style={{ width: '100%' }}
                  value={classSearch}
                  onChange={(e) => setClassSearch(e.target.value)}
                />
                
                <button className="btn-secondary" onClick={clearAllClasses} style={{ padding: '0 14px' }}>
                  Clear
                </button>
                <button className="btn-primary" onClick={selectAllClasses} style={{ padding: '0 14px' }}>
                  Popular
                </button>
              </div>

              <div className="class-filters-grid">
                {filteredClasses.map((cls) => {
                  const isSelected = activeClasses.includes(cls.id);
                  return (
                    <div 
                      key={cls.id}
                      className={`class-chip ${isSelected ? 'selected' : ''}`}
                      onClick={() => handleClassToggle(cls.id)}
                    >
                      {isSelected && <Check size={12} style={{ display: 'inline', marginRight: '4px' }} />}
                      {cls.name}
                    </div>
                  );
                })}
              </div>

              <div className="sidebar-divider"></div>

              {/* URL/IP Camera Stream connector */}
              <h3>IP Camera Connection</h3>
              <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                <input 
                  type="text"
                  placeholder="rtsp://admin:pass@192.168.1.100:554/stream"
                  className="custom-select"
                  value={rtspUrl}
                  onChange={(e) => setRtspUrl(e.target.value)}
                />
                <button className="btn-primary" onClick={handleRtspConnect}>
                  Connect
                </button>
              </div>

              <div className="sidebar-divider"></div>

              {/* Backend API Server Endpoint Config */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <h3 style={{ margin: 0 }}>Backend Server Endpoint</h3>
                <span className={`status-badge ${systemConnected ? '' : 'offline'}`} style={{ padding: '4px 10px', fontSize: '0.75rem' }}>
                  <div className="pulse-dot"></div>
                  {systemConnected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '12px' }}>
                For live Vercel deployments, enter your active Python FastAPI server host URL (e.g. Render, Railway, Hugging Face, or ngrok).
              </p>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input 
                  type="text"
                  placeholder="https://yolov8-backend.onrender.com or http://localhost:8000"
                  className="custom-select"
                  value={backendInput}
                  onChange={(e) => setBackendInput(e.target.value)}
                />
                <button 
                  className="btn-primary" 
                  onClick={() => handleSaveBackendUrl(backendInput)}
                  style={{ whiteSpace: 'nowrap' }}
                >
                  Save URL
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Backend Server Configuration Modal */}
        {showBackendModal && (
          <div className="modal-backdrop" onClick={() => setShowBackendModal(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Server size={20} style={{ color: 'var(--accent-cyan)' }} />
                  <h3 style={{ margin: 0, fontSize: '1.1rem' }}>Backend Server Configuration</h3>
                </div>
                <button 
                  className="btn-icon" 
                  onClick={() => setShowBackendModal(false)}
                  style={{ padding: '4px' }}
                >
                  <X size={18} />
                </button>
              </div>

              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: '1.4', margin: 0 }}>
                When deployed on <strong>Vercel</strong>, the dashboard connects to your remote Python FastAPI + YOLOv8 inference backend.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                  Backend Server URL
                </label>
                <input 
                  type="text"
                  placeholder="https://your-backend.onrender.com or http://localhost:8000"
                  className="custom-select"
                  value={backendInput}
                  onChange={(e) => setBackendInput(e.target.value)}
                />
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Stored in your browser's local cache. Leave blank for default origin.
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                <button 
                  className="btn-secondary" 
                  onClick={() => {
                    setBackendInput('');
                    handleSaveBackendUrl('');
                  }}
                >
                  Clear (Default)
                </button>
                <button 
                  className="btn-primary" 
                  onClick={() => handleSaveBackendUrl(backendInput)}
                >
                  Save & Connect
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
