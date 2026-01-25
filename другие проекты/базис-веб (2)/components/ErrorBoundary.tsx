
import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface ErrorBoundaryProps {
  children?: ReactNode;
  fallback?: ReactNode;
  componentName?: string;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null
    };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    // Update state so the next render will show the fallback UI.
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // You can also log the error to an error reporting service
    console.error(`Uncaught error in ${this.props.componentName || 'component'}:`, error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      
      return (
        <div className="flex flex-col items-center justify-center h-full w-full bg-[#1a1a1a] text-slate-300 p-8 text-center relative z-50 min-h-[300px]">
          <AlertTriangle className="text-red-500 mb-4" size={48} />
          <h2 className="text-xl font-bold text-white mb-2">
            Ошибка в {this.props.componentName || 'компоненте'}
          </h2>
          <p className="text-sm text-slate-500 mb-6 max-w-md">
            Произошла критическая ошибка рендеринга. Попробуйте перезагрузить компонент.
          </p>
          <div className="bg-slate-900 p-4 rounded text-left font-mono text-xs text-red-400 mb-6 max-w-lg overflow-auto w-full max-h-40 border border-red-900/30">
             {this.state.error?.message || "Unknown error"}
          </div>
          <button
            onClick={this.handleReset}
            className="flex items-center gap-2 px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-bold transition shadow-lg"
          >
            <RefreshCw size={18} /> Перезагрузить
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
