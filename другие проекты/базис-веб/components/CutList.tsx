
import React, { useMemo, useState } from 'react';
import { useProjectStore } from '../store/projectStore';
import { Material, EdgeThickness } from '../types';
import { FileText, Coins } from 'lucide-react';

interface CutListProps {
  materialLibrary: Material[];
}

const CutList: React.FC<CutListProps> = ({ materialLibrary }) => {
  const { panels } = useProjectStore();
  const [markup, setMarkup] = useState(150); // Наценка %

  const edgePrices: Record<EdgeThickness, number> = {
      'none': 0,
      '0.4': 35, // руб/м
      '1.0': 65,
      '2.0': 95
  };

  const workPrices = {
      cutPerM: 80, // Пиление
      drillPerHole: 25, // Сверление
      edgePerM: 45, // Наклейка кромки (работа)
      assembly: 500 // Сборка за модуль (условно)
  };

  const report = useMemo(() => {
    const matUsage: Record<string, { area: number, cost: number, name: string }> = {};
    let totalEdgeLength: Record<EdgeThickness, number> = { 'none': 0, '0.4': 0, '1.0': 0, '2.0': 0 };
    let totalHoles = 0;
    let cutLength = 0;

    panels.forEach(p => {
        const area = (p.width * p.height) / 1000000;
        const mat = materialLibrary.find(m => m.id === p.materialId) || materialLibrary[0];
        
        // Учет КИМ (Коэффициент Использования Материала) ~1.2 (20% обрезков)
        const wasteFactor = 1.2;
        
        if (!matUsage[mat.id]) matUsage[mat.id] = { area: 0, cost: 0, name: mat.name };
        matUsage[mat.id].area += area * wasteFactor;
        matUsage[mat.id].cost += (area * wasteFactor) * mat.pricePerM2;

        cutLength += (p.width + p.height) * 2 / 1000;

        (Object.keys(p.edging) as (keyof typeof p.edging)[]).forEach(side => {
            const type = p.edging[side];
            const length = (side === 'top' || side === 'bottom') ? p.width/1000 : p.height/1000;
            totalEdgeLength[type] += length;
        });

        totalHoles += (p.hardware || []).length;
    });

    const edgeMatCost = Object.entries(totalEdgeLength).reduce((acc, [type, len]) => acc + (len * edgePrices[type as EdgeThickness]), 0);
    const materialCost = Object.values(matUsage).reduce((acc, val) => acc + val.cost, 0);
    
    // Labor Calculation
    const laborCut = cutLength * workPrices.cutPerM;
    const laborEdge = Object.values(totalEdgeLength).reduce((a, b) => a + b, 0) * workPrices.edgePerM;
    const laborDrill = totalHoles * workPrices.drillPerHole;
    const laborTotal = laborCut + laborEdge + laborDrill;

    const primeCost = materialCost + edgeMatCost + laborTotal;
    const finalPrice = primeCost * (markup / 100 + 1);

    return { 
        matUsage, 
        materialCost, 
        edgeMatCost, 
        laborTotal, 
        primeCost, 
        finalPrice, 
        totalHoles 
    };
  }, [panels, materialLibrary, markup]);

  return (
    <div className="p-4 md:p-8 bg-slate-900 h-full overflow-y-auto text-slate-200 no-scrollbar">
      <div className="max-w-5xl mx-auto">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-end mb-8 border-b border-slate-700 pb-4 gap-4">
              <div>
                  <h2 className="text-2xl md:text-3xl font-bold flex items-center gap-3"><FileText className="text-blue-500" size={32}/> Коммерческое предложение</h2>
                  <p className="text-slate-400 mt-1">Расчет себестоимости и цены продажи</p>
              </div>
              <div className="flex items-center gap-4 w-full md:w-auto">
                  <div className="flex items-center bg-slate-800 rounded px-3 py-1 border border-slate-600 w-full md:w-auto justify-between">
                      <span className="text-xs text-slate-400 mr-2 uppercase font-bold">Наценка %</span>
                      <input 
                        type="number" 
                        value={markup} 
                        onChange={(e) => setMarkup(+e.target.value)} 
                        className="bg-transparent w-12 text-right font-bold focus:outline-none"
                      />
                  </div>
              </div>
          </div>

          {/* Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
              <div className="bg-slate-800 p-5 rounded-xl border border-slate-700 shadow-xl">
                  <div className="text-slate-400 text-xs font-bold uppercase mb-2">Листовые материалы</div>
                  <div className="text-2xl font-mono font-bold">{Math.round(report.materialCost).toLocaleString()} ₽</div>
                  <div className="text-slate-500 text-[10px] mt-2">С учетом КИМ 1.2</div>
              </div>
              <div className="bg-slate-800 p-5 rounded-xl border border-slate-700 shadow-xl">
                  <div className="text-slate-400 text-xs font-bold uppercase mb-2">Фурнитура и кромка</div>
                  <div className="text-2xl font-mono font-bold">{Math.round(report.edgeMatCost).toLocaleString()} ₽</div>
                  <div className="text-slate-500 text-[10px] mt-2">Комплектующие</div>
              </div>
              <div className="bg-slate-800 p-5 rounded-xl border border-slate-700 shadow-xl">
                  <div className="text-slate-400 text-xs font-bold uppercase mb-2">Работа (ФОТ)</div>
                  <div className="text-2xl font-mono font-bold">{Math.round(report.laborTotal).toLocaleString()} ₽</div>
                  <div className="text-slate-500 text-[10px] mt-2">Распил, присадка, кромка</div>
              </div>
              <div className="bg-blue-900/30 p-5 rounded-xl border border-blue-500/30 shadow-xl relative overflow-hidden">
                  <div className="absolute top-0 right-0 p-2 opacity-10"><Coins size={64}/></div>
                  <div className="text-blue-400 text-xs font-bold uppercase mb-2">Себестоимость</div>
                  <div className="text-3xl font-mono font-bold text-white">{Math.round(report.primeCost).toLocaleString()} ₽</div>
              </div>
          </div>

          {/* Details Table Container */}
          <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden shadow-2xl mb-8">
              <div className="overflow-x-auto no-scrollbar">
                  <table className="w-full text-left whitespace-nowrap">
                      <thead className="bg-slate-700 text-slate-300 text-xs uppercase tracking-widest">
                          <tr>
                              <th className="px-6 py-4">Материал</th>
                              <th className="px-6 py-4 text-center">Расход (м²)</th>
                              <th className="px-6 py-4 text-right">Цена закупки</th>
                              <th className="px-6 py-4 text-right">Сумма</th>
                          </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-700">
                          {(Object.values(report.matUsage) as Array<{name: string, area: number, cost: number}>).map((m, i) => (
                              <tr key={i} className="hover:bg-slate-750 transition">
                                  <td className="px-6 py-4 font-bold">{m.name}</td>
                                  <td className="px-6 py-4 text-center font-mono">{m.area.toFixed(2)}</td>
                                  <td className="px-6 py-4 text-right text-slate-400">{Math.round(m.cost / m.area)} ₽/м²</td>
                                  <td className="px-6 py-4 text-right font-bold">{Math.round(m.cost).toLocaleString()} ₽</td>
                              </tr>
                          ))}
                      </tbody>
                  </table>
              </div>
          </div>

          {/* Final Price */}
          <div className="bg-gradient-to-r from-slate-900 to-slate-800 p-8 rounded-2xl border border-slate-600 flex flex-col md:flex-row justify-between items-center shadow-2xl gap-4 text-center md:text-left">
              <div>
                  <div className="text-emerald-400 text-sm font-bold uppercase mb-1">Итоговая цена для клиента</div>
                  <div className="text-slate-400 text-xs">Включая наценку {markup}%</div>
              </div>
              <div className="text-5xl md:text-6xl font-mono font-extrabold text-white tracking-tight">
                  {Math.round(report.finalPrice).toLocaleString()} <span className="text-3xl font-normal text-slate-500">₽</span>
              </div>
          </div>
      </div>
    </div>
  );
};

export default CutList;
