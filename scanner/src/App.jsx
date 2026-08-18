import ScannerView from './components/ScannerView';
import { ErrorBoundary } from './components/ErrorBoundary';
import './App.css';

export default function App() {
  return (
    <div className="app-wrapper">
      <main>
        <ErrorBoundary>
          <ScannerView />
        </ErrorBoundary>
      </main>
    </div>
  );
}