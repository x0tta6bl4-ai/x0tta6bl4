import React from 'react';

interface QRCodeSVGProps {
  value: string;
  size?: number;
}

const QRCodeSVG: React.FC<QRCodeSVGProps> = ({ value, size = 64 }) => {
  const seed = value.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  const cells: React.ReactNode[] = [];
  const gridSize = 8;
  const cellSize = size / gridSize;

  const marker = (cx: number, cy: number) => (
    <g>
      <rect
        x={cx}
        y={cy}
        width={cellSize * 3}
        height={cellSize * 3}
        fill="black"
      />
      <rect
        x={cx + cellSize * 0.5}
        y={cy + cellSize * 0.5}
        width={cellSize * 2}
        height={cellSize * 2}
        fill="white"
      />
      <rect
        x={cx + cellSize}
        y={cy + cellSize}
        width={cellSize}
        height={cellSize}
        fill="black"
      />
    </g>
  );

  for (let y = 0; y < gridSize; y++) {
    for (let x = 0; x < gridSize; x++) {
      if ((x < 3 && y < 3) || (x > 4 && y < 3) || (x < 3 && y > 4)) continue;
      const isFilled = Math.sin(seed * (x + 1) * (y + 1)) > 0;
      if (isFilled)
        cells.push(
          <rect
            key={`${x}-${y}`}
            x={x * cellSize}
            y={y * cellSize}
            width={cellSize}
            height={cellSize}
            fill="black"
          />
        );
    }
  }

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <rect width={size} height={size} fill="white" />
      {marker(0, 0)}
      {marker(size - cellSize * 3, 0)}
      {marker(0, size - cellSize * 3)}
      {cells}
    </svg>
  );
};

export default QRCodeSVG;
