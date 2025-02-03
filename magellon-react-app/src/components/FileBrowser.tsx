import React, { useState, useEffect } from 'react';
import {
  Folder,
  File,
  ChevronRight,
  ArrowUp,
  Loader, ArrowUpIcon, FileIcon, FolderIcon
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
  const [hoveredPath, setHoveredPath] = useState<string | null>(null);

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
        <h2 className="text-xl font-semibold mb-4">File Browser</h2>

        {/* Breadcrumb navigation */}
        <div className="flex items-center gap-1 mb-4 text-sm overflow-x-auto">
          <button
              onClick={() => fetchDirectory('/')}
              className="text-blue-600 hover:text-blue-800 whitespace-nowrap"
          >
            root
          </button>
          {pathParts.map((part, index) => (
              <React.Fragment key={index}>
                <ChevronRight className="text-gray-400 flex-shrink-0" size={16} />
                <button
                    onClick={() => handleBreadcrumbClick(index)}
                    className="text-blue-600 hover:text-blue-800 whitespace-nowrap"
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
            <div className="flex flex-wrap gap-4 max-h-96 overflow-y-auto p-4">
              {currentPath !== '/' && (
                  <div
                      onClick={handleNavigateUp}
                      onMouseEnter={() => setHoveredPath('up')}
                      onMouseLeave={() => setHoveredPath(null)}
                      className={`relative h-16 w-16 bg-gray-50 rounded-lg flex flex-col items-center justify-center cursor-pointer border border-gray-200
              ${hoveredPath === 'up' ? 'bg-blue-50 border-blue-300 shadow-lg' : ''}`}
                  >
                    <ArrowUpIcon className={`${hoveredPath === 'up' ? 'text-blue-500' : 'text-gray-500'}`} size={24}/>
                  </div>
              )}

              {items.map((item) => (
                  <div
                      key={item.path}
                      onClick={() => handleItemClick(item)}
                      onMouseEnter={() => setHoveredPath(item.path)}
                      onMouseLeave={() => setHoveredPath(null)}
                      className={`relative h-16 w-16 bg-white rounded-lg p-1 flex flex-col items-center cursor-pointer border-2
              ${item.path === selectedPath ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}
              ${hoveredPath === item.path ? 'bg-blue-50 border-blue-300 shadow-lg' : ''}`}
                  >
                    {item.type === 'directory' ? (
                        <FolderIcon
                            className={`flex-shrink-0 mt-1 ${hoveredPath === item.path ? 'text-blue-500' : 'text-gray-500'}`}
                            size={40}
                        />
                    ) : (
                        <FileIcon
                            className={`flex-shrink-0 mt-1 ${hoveredPath === item.path ? 'text-blue-500' : 'text-gray-500'}`}
                            size={40}
                        />
                    )}
                    <div className="w-full flex-1 flex flex-col justify-start items-center">
                      <div className={`text-[10px] leading-tight text-center break-words line-clamp-2
                ${hoveredPath === item.path ? 'text-blue-600' : 'text-gray-600'}`}>
                        {item.name}
                      </div>
                      {item.is_session && (
                          <div className={`text-[8px] text-center
                  ${hoveredPath === item.path ? 'text-blue-500' : 'text-gray-500'}`}>
                            (session)
                          </div>
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