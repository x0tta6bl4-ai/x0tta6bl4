import React, { useMemo } from 'react';
import { Panel, Material, ProductionNorms } from '../../types';
import { BarChart3, Activity } from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

interface DashboardProps {
  panels: Panel[];
  materialLibrary: Material[];
  currentGlobalStage: string;
}

const Dashboard: React.FC<DashboardProps> = ({ panels, materialLibrary, currentGlobalStage }) => {
  const dashboardStats = useMemo(() => {
    const matCounts: Record<string, number> = {};
    panels.forEach(p => {
      const matName = materialLibrary.find(m => m.id === p.materialId)?.name.split(' ')[0] || p.materialId;
      matCounts[matName] = (matCounts[matName] || 0) + 1;
    });
    const barData = Object.entries(matCounts).map(([name, count]) => ({ name, count }));

    const completedTotal = panels.filter(p => p.productionStatus === 'completed').length;
    const pendingTotal = panels.length - completedTotal;
    const pieData = [
      { name: 'Готово', value: completedTotal, color: '#10b981' },
      { name: 'В работе', value: pendingTotal, color: '#3b82f6' },
    ];

    return { barData, pieData };
  }, [panels, materialLibrary]);

  return (
    <div className="h-full overflow-y-auto no-scrollbar p-6 space-y-6">
      <h2 className="text-2xl font-bold text-white mb-4 flex items-center gap-3">
        <BarChart3 size={32} className="text-blue-500" /> MES Аналитика
      </h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[#1a1a1a] p-4 rounded-xl border border-slate-700 shadow-xl">
          <h3 className="text-sm font-bold text-slate-400 mb-4 uppercase">Расход Деталей по Материалам</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dashboardStats.barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="name" stroke="#666" fontSize={10} />
                <YAxis stroke="#666" fontSize={10} />
                <Tooltip contentStyle={{ backgroundColor: '#222', borderColor: '#444' }} itemStyle={{ color: '#fff' }} />
                <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} barSize={40} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-[#1a1a1a] p-4 rounded-xl border border-slate-700 shadow-xl">
          <h3 className="text-sm font-bold text-slate-400 mb-4 uppercase">
            Статус Выполнения ({currentGlobalStage})
          </h3>
          <div className="h-64 flex justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={dashboardStats.pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {dashboardStats.pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: '#222', borderColor: '#444' }} itemStyle={{ color: '#fff' }} />
                <Legend verticalAlign="bottom" height={36} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="bg-[#1a1a1a] p-6 rounded-xl border border-slate-700 shadow-xl">
        <h3 className="text-sm font-bold text-slate-400 mb-4 uppercase flex items-center gap-2">
          <Activity size={16} /> Лог Активности
        </h3>
        <div className="space-y-4">
          {[1, 2, 3].map((_, i) => (
            <div key={i} className="flex gap-4 border-l-2 border-slate-700 pl-4 py-1 relative">
              <div className="absolute -left-[5px] top-2 w-2.5 h-2.5 rounded-full bg-slate-600 border-2 border-[#1a1a1a]"></div>
              <div className="text-xs text-slate-500 font-mono">10:{30 + i * 5}</div>
              <div>
                <div className="text-sm text-white">
                  Оператор завершил этап{' '}
                  <span className="text-blue-400 font-bold">{['Раскрой', 'Кромление', 'Присадка'][i]}</span> для
                  партии #1024-{i + 1}
                </div>
                <div className="text-xs text-slate-500">
                  Участок {i + 1} • Пользователь: Master
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
