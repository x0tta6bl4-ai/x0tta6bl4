import React from 'react';
import { Panel, Material } from '../../types';
import QRCodeSVG from './QRCodeSVG';

interface ProductionLabelProps {
  panel: Panel;
  material?: Material;
  orderId: string;
  index: number;
}

const ProductionLabel: React.FC<ProductionLabelProps> = ({
  panel,
  material,
  orderId,
  index,
}) => (
  <div className="bg-white text-black p-2 border border-slate-300 w-[300px] h-[180px] flex flex-col justify-between shadow-sm break-inside-avoid relative overflow-hidden print:border-black">
    <div className="flex justify-between items-start border-b border-black pb-1 mb-1">
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider">
          Заказ №{orderId}
        </div>
        <div className="text-lg font-bold leading-none mt-1">
          {panel.name.substring(0, 18)}
        </div>
      </div>
      <div className="text-2xl font-bold font-mono">#{index + 1}</div>
    </div>

    <div className="flex gap-2 h-full">
      <div className="flex-1 flex flex-col justify-between">
        <div className="text-xs font-mono">
          <div className="flex justify-between">
            <span>L:</span> <b>{panel.width}</b>
          </div>
          <div className="flex justify-between">
            <span>W:</span> <b>{panel.height}</b>
          </div>
          <div className="mt-1 text-[10px] text-slate-600 leading-tight">
            {material?.name}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-0.5 text-[8px] border border-black mt-2 text-center">
          <div className="bg-slate-200 p-0.5">КРОМКА</div>
          <div className="col-span-2 grid grid-cols-2">
            <div className="border-r border-b border-black/20">
              {panel.edging.top !== 'none' ? 'TOP' : '-'}
            </div>
            <div className="border-b border-black/20">
              {panel.edging.right !== 'none' ? 'RGT' : '-'}
            </div>
            <div className="border-r border-black/20">
              {panel.edging.bottom !== 'none' ? 'BTM' : '-'}
            </div>
            <div>{panel.edging.left !== 'none' ? 'LFT' : '-'}</div>
          </div>
        </div>
      </div>

      <div className="flex flex-col items-center justify-center border-l border-slate-200 pl-2">
        <QRCodeSVG value={panel.id} size={80} />
        <div className="text-[8px] font-mono mt-1">{panel.id.slice(-8)}</div>
      </div>
    </div>

    <div className="mt-1 flex gap-1">
      {panel.hardware && panel.hardware.length > 0 && (
        <span className="bg-black text-white text-[9px] px-1 rounded">
          ПРИСАДКА
        </span>
      )}
      {panel.groove?.enabled && (
        <span className="bg-black text-white text-[9px] px-1 rounded">ПАЗ</span>
      )}
      {panel.currentStage === 'shipping' && (
        <span className="bg-green-600 text-white text-[9px] px-1 rounded">
          ГОТОВО
        </span>
      )}
    </div>
  </div>
);

export default ProductionLabel;
