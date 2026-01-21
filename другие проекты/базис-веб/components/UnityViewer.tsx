
import React, { useEffect, useState } from 'react';
import { Unity, useUnityContext } from 'react-unity-webgl';
import { Panel } from '../types';
import { Loader2, AlertTriangle, RefreshCw } from 'lucide-react';

interface UnityViewerProps {
  panels: Panel[];
}

// NOTE: In a real environment, these paths would point to the /public folder
// where the Unity Build output (WASM/Data/Loader) is stored.
const UNITY_BUILD_CONFIG = {
  loaderUrl: "/unity/build.loader.js",
  dataUrl: "/unity/build.data",
  frameworkUrl: "/unity/build.framework.js",
  codeUrl: "/unity/build.wasm",
};

const UnityViewer: React.FC<UnityViewerProps> = ({ panels }) => {
  const [loadError, setLoadError] = useState(false);
  const [progress, setProgress] = useState(0);

  const { unityProvider, isLoaded, loadingProgression, sendMessage, addEventListener, removeEventListener } = useUnityContext({
    loaderUrl: UNITY_BUILD_CONFIG.loaderUrl,
    dataUrl: UNITY_BUILD_CONFIG.dataUrl,
    frameworkUrl: UNITY_BUILD_CONFIG.frameworkUrl,
    codeUrl: UNITY_BUILD_CONFIG.codeUrl,
  });

  // Sync Progress state
  useEffect(() => {
    setProgress(Math.round(loadingProgression * 100));
  }, [loadingProgression]);

  // Handle Missing Build Files (Simulation Check)
  // In a real app, the browser would throw a 404, we catch it via window error or timeout
  useEffect(() => {
    const timer = setTimeout(() => {
        if (progress === 0) {
            // Assume 404 if no progress after 2 seconds in this demo environment
            setLoadError(true);
        }
    }, 2000);
    return () => clearTimeout(timer);
  }, [progress]);

  // Send Data Bridge
  useEffect(() => {
    if (isLoaded) {
      try {
        const payload = JSON.stringify({ panels });
        // Assuming C# script has: public void LoadProject(string json)
        sendMessage("BridgeController", "LoadProject", payload);
      } catch (e) {
        console.error("Unity Bridge Error:", e);
      }
    }
  }, [isLoaded, panels, sendMessage]);

  // Mock function to listen for Unity events (e.g., selection)
  useEffect(() => {
    const handleUnitySelect = (...args: any[]) => {
        const id = args[0];
        console.log("Unity selected panel:", id);
        return id;
    };

    if (isLoaded) {
        addEventListener("OnPanelSelect", handleUnitySelect as any);
        return () => {
            removeEventListener("OnPanelSelect", handleUnitySelect as any);
        };
    }
  }, [isLoaded, addEventListener, removeEventListener]);

  if (loadError) {
      return (
          <div className="w-full h-full flex flex-col items-center justify-center bg-black text-slate-300 p-8 text-center">
              <div className="bg-red-900/20 p-6 rounded-xl border border-red-500/30 max-w-md">
                  <AlertTriangle size={48} className="text-red-500 mx-auto mb-4"/>
                  <h3 className="text-xl font-bold text-white mb-2">Unity Build Not Found</h3>
                  <p className="text-sm text-slate-400 mb-4">
                      Интеграция настроена, но файлы сборки отсутствуют по пути <code>/public/unity/</code>.
                  </p>
                  <p className="text-xs text-slate-500 font-mono bg-black p-2 rounded text-left">
                      Expected: {UNITY_BUILD_CONFIG.loaderUrl}
                  </p>
                  <div className="mt-6 text-xs text-slate-400">
                      Для работы этого режима необходимо собрать проект в Unity (WebGL Platform) и поместить файлы в папку public.
                  </div>
              </div>
          </div>
      );
  }

  return (
    <div className="w-full h-full relative bg-black">
      {!isLoaded && (
        <div className="absolute inset-0 flex flex-col items-center justify-center z-10">
          <Loader2 size={48} className="text-blue-500 animate-spin mb-4" />
          <div className="text-white font-bold text-lg tracking-wider">LOADING ENGINE</div>
          <div className="w-64 h-2 bg-slate-800 rounded-full mt-4 overflow-hidden">
              <div className="h-full bg-blue-600 transition-all duration-300" style={{ width: `${progress}%` }}></div>
          </div>
          <div className="text-xs text-slate-500 mt-2">{progress}%</div>
        </div>
      )}
      
      <Unity 
        unityProvider={unityProvider} 
        style={{ width: "100%", height: "100%", visibility: isLoaded ? "visible" : "hidden" }} 
      />
      
      <div className="absolute bottom-4 left-4 z-20 pointer-events-none">
          <div className="bg-black/80 backdrop-blur border border-white/10 px-3 py-1 rounded text-[10px] text-white font-mono flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
              UNITY WEBGL 2023.2
          </div>
      </div>
    </div>
  );
};

export default UnityViewer;
