import React from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { RootState } from '../app/store';
import { clearError } from '../store/errorSlice';
import { Button } from '../components/ui/button';

const ErrorPage: React.FC = () => {
  const dispatch = useDispatch();
  const { message, status } = useSelector((state: RootState) => state.error);

  const handleClearError = () => {
    dispatch(clearError());
    // Optionally, navigate to the home page or previous page
    window.history.back();
  };

  if (!message) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-gray-800 bg-opacity-75 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-8 max-w-md w-full text-center">
        <h2 className="text-2xl font-bold text-red-600 mb-4">An Error Occurred</h2>
        {status && <p className="text-lg mb-2">Status: {status}</p>}
        <p className="text-gray-700 mb-6">{message}</p>
        <Button onClick={handleClearError} className="bg-red-600 hover:bg-red-700">
          Go Back
        </Button>
      </div>
    </div>
  );
};

export default ErrorPage;
