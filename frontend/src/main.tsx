// src/main.tsx (Updated)
import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ToastContainer } from 'react-toastify';
import { Provider } from 'react-redux';
import { PersistGate } from 'redux-persist/integration/react';  // Add this
import { store, persistor } from './app/store';  // Import persistor
import 'react-toastify/dist/ReactToastify.css'; // ✅ Make sure this is imported
import '@livekit/components-styles';
import App from './App';
import { ThemeProvider, useTheme } from './hooks/useTheme';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

const AppBootstrap: React.FC = () => {
  const { resolvedTheme } = useTheme();

  return (
    <Provider store={store}>
      <PersistGate loading={<div>Loading...</div>} persistor={persistor}>  {/* Wrap for persistence */}
        <QueryClientProvider client={queryClient}>
          <App />
          <ToastContainer
            position="top-right"
            autoClose={5000}
            hideProgressBar={false}
            newestOnTop={false}
            closeOnClick
            rtl={false}
            pauseOnFocusLoss
            draggable
            pauseOnHover
            theme={resolvedTheme}
          />
        </QueryClientProvider>
      </PersistGate>
    </Provider>
  );
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <AppBootstrap />
    </ThemeProvider>
  </React.StrictMode>
);
