import React, { useState, useEffect } from 'react';
import {
  Folder,
  File,
  ChevronRight,
  ArrowUp,
  Loader
} from 'lucide-react';

interface FileItem {
  name: string;
  path: string;
  type: 'directory' | 'file';
  is_session: boolean;
}

interface FileBrowserProps {
  onSelect: (path: string) => void;
  initialPath?: string;
}

const FileBrowser = ({ onSelect, initialPath = '/gpfs' }: FileBrowserProps) => {
  const [currentPath, setCurrentPath] = useState(initialPath);
  const [items, setItems] = useState<FileItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  const fetchDirectory = async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`http://localhost:8000/web/files/browse?path=${encodeURIComponent(path)}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setItems(data.items);
      setCurrentPath(data.current_path);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDirectory(currentPath);
  }, [currentPath]);

  const handleItemClick = (item: FileItem) => {
    if (item.type === 'directory') {
      fetchDirectory(item.path);
    } else if (item.is_session) {
      setSelectedPath(item.path);
      onSelect(item.path);
    }
  };

  const handleNavigateUp = () => {
    const parentPath = currentPath.split('/').slice(0, -1).join('/');
    if (parentPath) {
      fetchDirectory(parentPath);
    }
  };

  const pathParts = currentPath.split('/').filter(Boolean);

  const handleBreadcrumbClick = (index: number) => {
    const newPath = '/' + pathParts.slice(0, index + 1).join('/');
    fetchDirectory(newPath);
  };

  return (
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-xl font-semibold mb-4">
          File Browser
        </h2>

        {/* Breadcrumb navigation */}
        <div className="flex items-center gap-1 mb-4 text-sm">
          <button
              onClick={() => fetchDirectory('/')}
              className="text-blue-600 hover:text-blue-800"
          >
            root
          </button>
          {pathParts.map((part, index) => (
              <React.Fragment key={index}>
                <ChevronRight className="text-gray-400" size={16} />
                <button
                    onClick={() => handleBreadcrumbClick(index)}
                    className="text-blue-600 hover:text-blue-800"
                >
                  {part}
                </button>
              </React.Fragment>
          ))}
        </div>

        {error && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
              {error}
            </div>
        )}

        {loading ? (
            <div className="flex justify-center items-center py-12">
              <Loader className="animate-spin text-blue-500" size={32} />
            </div>
        ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 max-h-96 overflow-y-auto p-4">
              {currentPath !== '/' && (
                  <div
                      onClick={handleNavigateUp}
                      className="bg-gray-50 rounded-lg shadow-sm p-4 flex items-center gap-3 cursor-pointer transform transition-all duration-200 hover:shadow-md hover:scale-105 hover:bg-gray-100 border border-gray-200"
                  >
                    <ArrowUp className="text-gray-500" size={32} />
                    <span className="font-medium">..</span>
                  </div>
              )}

              {items.map((item) => (
                  <div
                      key={item.path}
                      onClick={() => handleItemClick(item)}
                      className={`bg-white rounded-lg shadow-sm p-4 flex items-center gap-3 cursor-pointer transform transition-all duration-200 hover:shadow-md hover:scale-105 border border-gray-200
                ${item.path === selectedPath ? 'ring-2 ring-blue-500 bg-blue-50' : 'hover:bg-gray-50'}
              `}
                  >
                    {item.type === 'directory' ? (
                        <Folder className="text-blue-500 flex-shrink-0" size={32} />
                    ) : (
                        <File className="text-gray-500 flex-shrink-0" size={32} />
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="font-medium truncate">{item.name}</div>
                      {item.is_session && (
                          <span className="text-xs text-gray-500">(session)</span>
                      )}
                    </div>
                  </div>
              ))}
            </div>
        )}

        {selectedPath && (
            <div className="mt-4 text-sm text-green-600">
              Selected: {selectedPath}
            </div>
        )}
      </div>
  );
};

export default FileBrowser;