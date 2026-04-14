import React, { useState, useEffect } from 'react';
import {
  ChevronRight,
  Loader, ArrowUpIcon, FileIcon, FolderIcon
} from 'lucide-react';
import { Box, Typography, Button } from '@mui/material';
import getAxiosClient from '../api/AxiosClient.ts';
import { settings } from '../config/settings.ts';

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

const apiClient = getAxiosClient(settings.ConfigData.SERVER_API_URL);

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
      const response = await apiClient.get('/web/files/browse', {
        params: { path }
      });
      setItems(response.data.items);
      setCurrentPath(response.data.current_path);
    } catch (err: any) {
      if (err.response?.status === 401) {
        setError('Please login to browse files');
      } else if (err.response?.status === 403) {
        setError('You do not have permission to browse this directory');
      } else {
        setError(err.response?.data?.detail || err.message || 'An error occurred');
      }
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

  const tileSx = (isSelected: boolean, isHovered: boolean) => ({
    position: 'relative',
    height: 64,
    width: 64,
    borderRadius: 1.5,
    p: 0.5,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    cursor: 'pointer',
    border: '2px solid',
    borderColor: isSelected ? '#3b82f6' : isHovered ? '#93c5fd' : '#e5e7eb',
    bgcolor: isSelected || isHovered ? '#eff6ff' : '#ffffff',
    boxShadow: isHovered ? 3 : 0,
    transition: 'all 120ms',
  });

  return (
    <Box sx={{ bgcolor: '#ffffff', borderRadius: 2, boxShadow: 3, p: 3 }}>
      <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>File Browser</Typography>

      {/* Breadcrumb navigation */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 2, fontSize: 14, overflowX: 'auto' }}>
        <Button
          size="small"
          onClick={() => fetchDirectory('/')}
          sx={{ color: '#2563eb', whiteSpace: 'nowrap', minWidth: 'auto', textTransform: 'none', '&:hover': { color: '#1e40af', bgcolor: 'transparent' } }}
        >
          root
        </Button>
        {pathParts.map((part, index) => (
          <React.Fragment key={index}>
            <ChevronRight color="#9ca3af" size={16} style={{ flexShrink: 0 }} />
            <Button
              size="small"
              onClick={() => handleBreadcrumbClick(index)}
              sx={{ color: '#2563eb', whiteSpace: 'nowrap', minWidth: 'auto', textTransform: 'none', '&:hover': { color: '#1e40af', bgcolor: 'transparent' } }}
            >
              {part}
            </Button>
          </React.Fragment>
        ))}
      </Box>

      {error && (
        <Box sx={{ bgcolor: '#fee2e2', border: '1px solid #f87171', color: '#b91c1c', px: 2, py: 1.5, borderRadius: 1, mb: 2 }}>
          {error}
        </Box>
      )}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 6 }}>
          <Loader color="#3b82f6" size={32} style={{ animation: 'spin 1s linear infinite' }} />
          <Box component="style">{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</Box>
        </Box>
      ) : (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, maxHeight: 384, overflowY: 'auto', p: 2 }}>
          {currentPath !== '/' && (
            <Box
              onClick={handleNavigateUp}
              onMouseEnter={() => setHoveredPath('up')}
              onMouseLeave={() => setHoveredPath(null)}
              sx={{
                position: 'relative',
                height: 64,
                width: 64,
                bgcolor: hoveredPath === 'up' ? '#eff6ff' : '#f9fafb',
                borderRadius: 1.5,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                border: '1px solid',
                borderColor: hoveredPath === 'up' ? '#93c5fd' : '#e5e7eb',
                boxShadow: hoveredPath === 'up' ? 3 : 0,
              }}
            >
              <ArrowUpIcon color={hoveredPath === 'up' ? '#3b82f6' : '#6b7280'} size={24}/>
            </Box>
          )}

          {items.map((item) => {
            const isSelected = item.path === selectedPath;
            const isHovered = hoveredPath === item.path;
            return (
              <Box
                key={item.path}
                onClick={() => handleItemClick(item)}
                onMouseEnter={() => setHoveredPath(item.path)}
                onMouseLeave={() => setHoveredPath(null)}
                sx={tileSx(isSelected, isHovered)}
              >
                {item.type === 'directory' ? (
                  <FolderIcon color={isHovered ? '#3b82f6' : '#6b7280'} size={40} style={{ flexShrink: 0, marginTop: 4 }} />
                ) : (
                  <FileIcon color={isHovered ? '#3b82f6' : '#6b7280'} size={40} style={{ flexShrink: 0, marginTop: 4 }} />
                )}
                <Box sx={{ width: '100%', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-start', alignItems: 'center' }}>
                  <Box
                    sx={{
                      fontSize: '10px',
                      lineHeight: 1.1,
                      textAlign: 'center',
                      wordBreak: 'break-word',
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                      color: isHovered ? '#2563eb' : '#4b5563',
                    }}
                  >
                    {item.name}
                  </Box>
                  {item.is_session && (
                    <Box sx={{ fontSize: '8px', textAlign: 'center', color: isHovered ? '#3b82f6' : '#6b7280' }}>
                      (session)
                    </Box>
                  )}
                </Box>
              </Box>
            );
          })}
        </Box>
      )}

      {selectedPath && (
        <Box sx={{ mt: 2, fontSize: 14, color: '#16a34a' }}>
          Selected: {selectedPath}
        </Box>
      )}
    </Box>
  );
};

export default FileBrowser;
