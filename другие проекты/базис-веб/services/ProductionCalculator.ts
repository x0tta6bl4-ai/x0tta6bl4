import { Panel, ProductionNorms } from '../types';

export const calculateNorms = (panels: Panel[]): ProductionNorms => {
  const totalAreaM2 = panels.reduce((acc, p) => acc + (p.width * p.height) / 1000000, 0);
  const estimatedSheets = Math.ceil(totalAreaM2 / 5);
  const cuttingTime = Math.max(20, estimatedSheets * 20);

  let totalEdges = 0;
  panels.forEach((p) => {
    if (p.edging.top !== 'none') totalEdges++;
    if (p.edging.bottom !== 'none') totalEdges++;
    if (p.edging.left !== 'none') totalEdges++;
    if (p.edging.right !== 'none') totalEdges++;
  });
  const edgingTime = Math.ceil(totalEdges * 0.5);

  const panelsWithHw = panels.filter((p) => p.hardware && p.hardware.length > 0).length;
  const drillingTime = Math.ceil(panelsWithHw * 2);

  let assemblyTime = 30;
  panels.forEach((p) => {
    if (p.openingType === 'drawer') assemblyTime += 15;
    if (p.openingType !== 'none' && p.openingType !== 'drawer') assemblyTime += 10;
    if (p.layer === 'shelves') assemblyTime += 5;
  });

  return {
    cuttingTime,
    edgingTime,
    drillingTime,
    assemblyTime,
    totalTimeMinutes: cuttingTime + edgingTime + drillingTime + assemblyTime,
  };
};

export const generateCNCCSV = (panels: Panel[], materialLibrary: any[]): string => {
  let csv = 'DetalID;Name;L;W;TH;Material;Qty;OpType;X;Y;Z;Diam;Depth\n';
  panels.forEach((p, idx) => {
    const mat = materialLibrary.find((m) => m.id === p.materialId);
    const baseLine = `${idx + 1};${p.name};${p.width};${p.height};${p.depth};${mat?.name || 'Unknown'};1`;
    p.hardware.forEach((h) => {
      let depth = h.depth || 13;
      if (h.type === 'dowel') depth = 30;
      csv += `${baseLine};DRILL;${h.x};${h.y};0;${h.diameter || 5};${depth}\n`;
    });
    if (p.groove && p.groove.enabled) {
      csv += `${baseLine};GROOVE;${p.groove.offset};0;0;${p.groove.width};${p.groove.depth}\n`;
    }
  });
  return csv;
};

export const downloadCSV = (csv: string, filename: string) => {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};
