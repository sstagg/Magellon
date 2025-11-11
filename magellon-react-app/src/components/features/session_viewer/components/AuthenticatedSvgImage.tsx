/**
 * Authenticated SVG Image Component
 * Renders an SVG <image> element with authentication
 */

import React from 'react';
import { useAuthenticatedImage } from '../../../../hooks/useAuthenticatedImage';

interface AuthenticatedSvgImageProps {
  x: number;
  y: number;
  width: number;
  height: number;
  href: string;
  dataName: string;
  alt?: string;
  style?: React.CSSProperties;
  onMouseOver?: () => void;
  onMouseOut?: () => void;
  onClick?: () => void;
}

export const AuthenticatedSvgImage: React.FC<AuthenticatedSvgImageProps> = ({
  x,
  y,
  width,
  height,
  href,
  dataName,
  style,
  onMouseOver,
  onMouseOut,
  onClick
}) => {
  const { imageUrl, isLoading, error } = useAuthenticatedImage(href);

  // If loading or error, render placeholder rect
  if (isLoading || error || !imageUrl) {
    return (
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={isLoading ? '#333' : '#555'}
        data-name={dataName}
      />
    );
  }

  return (
    <image
      x={x}
      y={y}
      width={width}
      height={height}
      href={imageUrl}
      data-name={dataName}
      onMouseOver={onMouseOver}
      onMouseOut={onMouseOut}
      onClick={onClick}
      style={style}
    />
  );
};
