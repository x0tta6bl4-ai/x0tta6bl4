
import React, { useState, useEffect } from 'react';
import { X, ArrowRight } from 'lucide-react';

export const OnboardingTour: React.FC = () => {
    const [step, setStep] = useState(0);
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        const seen = localStorage.getItem('bazis_tour_seen');
        if (!seen) {
            setTimeout(() => setVisible(true), 1000);
        }
    }, []);

    const handleDismiss = () => {
        setVisible(false);
        localStorage.setItem('bazis_tour_seen', 'true');
    };

    const steps = [
        { title: 'Добро пожаловать!', text: 'BazisPro Web - это профессиональный инструмент для проектирования мебели. Давайте быстро осмотримся.' },
        { title: 'Мастер Шкафа', text: 'Начните с настройки габаритов, материалов и наполнения в панели слева. Используйте кнопки "Полка" и "Ящик".' },
        { title: '3D Сцена', text: 'В центре экрана находится ваша модель. Вращайте (ЛКМ), перемещайте (ПКМ) и масштабируйте (Колесо) для осмотра.' },
        { title: 'Экспорт и Производство', text: 'Готовый проект можно выгрузить в DXF для станка ЧПУ, получить карту раскроя или смету в один клик.' },
    ];

    if (!visible) return null;

    return (
        <div className="fixed bottom-8 left-8 z-[100] max-w-sm w-full bg-blue-600 text-white p-6 rounded-xl shadow-2xl animate-in slide-in-from-bottom-10 fade-in duration-500 border border-blue-400">
            <button onClick={handleDismiss} className="absolute top-2 right-2 text-blue-200 hover:text-white"><X size={16}/></button>
            <div className="flex flex-col gap-4">
                <div>
                    <h3 className="text-lg font-bold mb-2">{steps[step].title}</h3>
                    <p className="text-blue-100 text-sm leading-relaxed">{steps[step].text}</p>
                </div>
                <div className="flex justify-between items-center mt-2">
                    <div className="flex gap-1">
                        {steps.map((_, i) => (
                            <div key={i} className={`w-2 h-2 rounded-full ${i === step ? 'bg-white' : 'bg-blue-800'}`} />
                        ))}
                    </div>
                    <button 
                        onClick={() => {
                            if (step < steps.length - 1) setStep(step + 1);
                            else handleDismiss();
                        }}
                        className="flex items-center gap-1 font-bold text-sm hover:underline"
                    >
                        {step < steps.length - 1 ? 'Далее' : 'Начать'} <ArrowRight size={16}/>
                    </button>
                </div>
            </div>
        </div>
    );
};
