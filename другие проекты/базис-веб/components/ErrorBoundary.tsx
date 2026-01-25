import React, { ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props {
  children?: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends React.Component<Props, State> {

  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      
      return (
        <div className="flex flex-col items-center justify-center h-full w-full bg-[#1a1a1a] text-slate-300 p-8 text-center">
          <AlertTriangle className="text-red-500 mb-4" size={48} />
          <h2 className="text-xl font-bold text-white mb-2">Что-то пошло не так в 3D сцене</h2>
          <p className="text-sm text-slate-500 mb-6 max-w-md">
            Произошла критическая ошибка рендеринга. Попробуйте перезагрузить сцену.
          </p>
          <div className="bg-slate-900 p-4 rounded text-left font-mono text-xs text-red-400 mb-6 max-w-lg overflow-auto w-full">
             {this.state.error?.message}
          </div>
          <button
            onClick={this.handleReset}
            className="flex items-center gap-2 px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-bold transition"
          >
            <RefreshCw size={18} /> Перезагрузить компонент
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;