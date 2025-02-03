import React, { useState, useRef } from 'react';
import * as tus from 'tus-js-client';

interface TusUploaderProps {
  endpoint: string;  // Your tusd server endpoint
  onSuccess?: (uploadUrl: string) => void;
  onError?: (error: Error) => void;
  onProgress?: (progress: number) => void;
}

const TusUploader: React.FC<TusUploaderProps> = ({
  endpoint,
  onSuccess,
  onError,
  onProgress,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const uploadRef = useRef<tus.Upload | null>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setProgress(0);
    }
  };

  const startUpload = async () => {
    if (!file) return;

    setIsUploading(true);

    try {
      // Create a new tus upload instance
      uploadRef.current = new tus.Upload(file, {
        endpoint,
        retryDelays: [0, 3000, 5000, 10000, 20000],
        metadata: {
          filename: file.name,
          filetype: file.type
        },
        onError: (error) => {
          console.error('Upload failed:', error);
          setIsUploading(false);
          if (onError) onError(error);
        },
        onProgress: (bytesUploaded, bytesTotal) => {
          const percentage = (bytesUploaded / bytesTotal) * 100;
          setProgress(percentage);
          if (onProgress) onProgress(percentage);
        },
        onSuccess: () => {
          console.log('Upload completed successfully');
          setIsUploading(false);
          if (uploadRef.current && onSuccess) {
            onSuccess(uploadRef.current.url);
          }
        }
      });

      // Start the upload
      uploadRef.current.start();
    } catch (error) {
      console.error('Error initiating upload:', error);
      setIsUploading(false);
      if (onError && error instanceof Error) onError(error);
    }
  };

  const cancelUpload = () => {
    if (uploadRef.current) {
      uploadRef.current.abort();
      setIsUploading(false);
      setProgress(0);
    }
  };

  return (
    <div className="p-4 border rounded">
      <input
        type="file"
        onChange={handleFileSelect}
        disabled={isUploading}
        className="mb-4"
      />
      
      {file && (
        <div className="mt-2">
          <p className="text-sm">Selected file: {file.name}</p>
          <p className="text-sm">Size: {(file.size / (1024 * 1024)).toFixed(2)} MB</p>
        </div>
      )}

      {progress > 0 && (
        <div className="mt-4">
          <div className="w-full bg-gray-200 rounded">
            <div
              className="bg-blue-600 rounded h-2"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-sm mt-1">{Math.round(progress)}% uploaded</p>
        </div>
      )}

      <div className="mt-4 space-x-2">
        <button
          onClick={startUpload}
          disabled={!file || isUploading}
          className="px-4 py-2 bg-blue-500 text-white rounded disabled:opacity-50"
        >
          {isUploading ? 'Uploading...' : 'Start Upload'}
        </button>
        
        {isUploading && (
          <button
            onClick={cancelUpload}
            className="px-4 py-2 bg-red-500 text-white rounded"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  );
};

export default TusUploader;

// Usage example:
/*

            <TusUploader
                endpoint="http://localhost:83/files/"
                onSuccess={(uploadUrl) => {
                    console.log('File available at:', uploadUrl);
                }}
            />


import TusUploader from './TusUploader';

const App = () => {
  return (
    <TusUploader
      endpoint="https://your-tusd-server.com/files/"
      onSuccess={(uploadUrl) => {
        console.log('Upload completed. File available at:', uploadUrl);
      }}
      onError={(error) => {
        console.error('Upload failed:', error);
      }}
      onProgress={(progress) => {
        console.log('Upload progress:', progress);
      }}
    />
  );
};
*/