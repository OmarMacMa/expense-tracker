import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Button } from '@/components/ui/button';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="flex min-h-[400px] flex-col items-center justify-center p-8 text-center">
          <div
            className="rounded-xl bg-white p-8"
            style={{ boxShadow: 'var(--shadow-card)' }}
          >
            <h2 className="text-xl font-semibold text-[#1D1B20]">
              Something went wrong
            </h2>
            <p className="mt-2 text-sm text-[#615D69]">
              An unexpected error occurred. Please try again.
            </p>
            <Button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="mt-4"
            >
              Try again
            </Button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
