# Сборка рабочей станции — ~147 822 ₽

Разработка систем защиты информации (компиляция ядра Linux, eBPF-программы, ML-модели CUDA)

## Спецификация (финальная)

| № | Компонент | Модель | Характеристики | Цена | Магазин | Ссылка |
|:-:|:----------|:-------|:--------------|:----:|:--------|:-------|
| 1 | **Процессор** | AMD Ryzen 9 9900X Tray | 12 ядер / 24 потока, 4.4-5.6 ГГц, TDP 120 Вт | 32 850 ₽ | Komtek | [komtek.net.ru](https://komtek.net.ru/processor-amd-ryzen-r9-9900x-tray-100-000000662/) |
| 2 | **Материнская плата** | MSI PRO B650-P WIFI | ATX, AM5, B650, 4×DDR5, Wi-Fi 6E, 2.5GbE | 11 120 ₽ | Komtek | [komtek.net.ru](https://komtek.net.ru/materinskaya-plata-msi-pro-b650-p-wifi/) |
| 3 | **ОЗУ** | Crucial 32GB DDR5-5600 (CT32G56C46U5) | 32 ГБ, DDR5-5600 | 37 600 ₽ | Komtek | [komtek.net.ru](https://komtek.net.ru/operativnaya-pamyat-crucial-32gb-ddr5-5600mhz-ct32g56c46u5/) |
| 4 | **SSD** | ADATA XPG GAMMIX S60 1TB PCIe 4.0 | 1 ТБ, M.2 NVMe PCIe 4.0 | 11 610 ₽ | Komtek | [komtek.net.ru](https://komtek.net.ru/nakopitel-ssd-m.2-1tb-adata-xpg-gammix-s60-agammixs60-1t-cs/) |
| 5 | **Видеокарта** | Asus GeForce RTX 4060 Ti 8GB | 8 ГБ GDDR6, CUDA 4352 ядра | 38 513 ₽ | Ozon | [Ozon](https://ozon.ru/t/8q2F5Vh) |
| 6 | **Блок питания** | DeepCool PQ750G (GamerStorm) | 750 Вт, ATX 3.1, 80+ Gold, модульный, японские конденсаторы | 7 310 ₽ | Komtek | [komtek.net.ru](https://komtek.net.ru/blok-pitaniya-750w-deepcool-pq750g/) |
| 7 | **Кулер CPU** | ID-Cooling SE-207-XT SLIM | 2-секционный, 120мм, 220 Вт TDP, 135 мм высота | 2 720 ₽ | Komtek | [komtek.net.ru](https://komtek.net.ru/kuler-dlya-processora-id-cooling-se-207-xt-slim/) |
| 8 | **Корпус** | 1STPLAYER TRILOBITE T7-P Black | Midi Tower ATX, GPU до 340 мм, кулер до 185 мм | 4 220 ₽ | Komtek | [komtek.net.ru](https://komtek.net.ru/korpus-1stplayer-trilobite-t7-p-black-bez-bp-t7-p-bk-4f1/) |
| 9 | **Сетевая карта** | ORIENT XWT-INT226PE (Intel I226-V) | 2.5GbE PCIe, драйвер igc, AF_XDP zero-copy | 1 879 ₽ | Ozon | [Ozon](https://www.ozon.ru/search/?text=ORIENT+XWT-INT226PE) |
| | | | **ИТОГО ПК** | **~147 822 ₽** | | |

## Проверка совместимости

| Компоненты | Статус |
|:-----------|:-------|
| CPU (AM5) + Плата (AM5) | ✅ |
| CPU (120W TDP) + Кулер (220W TDP) | ✅ Запас 100W |
| Кулер (135 мм) + Корпус (до 185 мм) | ✅ Запас 50 мм |
| GPU (250 мм) + Корпус (до 340 мм) | ✅ Запас 90 мм |
| БП (750W) + Система (~396W) | ✅ Запас 354W |
| БП ATX 3.1, 80+ Gold, модульный | ✅ Премиум |
| Intel I226-V + AF_XDP zero-copy | ✅ Драйвер igc |

## Почему Intel I226-V

eBPF/XDP программы обрабатывают пакеты до того как они попадают в сетевой стек ядра. Intel I226-V — улучшенная версия I225-V (исправлены баги ранних степпингов). Драйвер `igc` поддерживает AF_XDP zero-copy полностью. Встроенные Realtek на материнских платах не имеют этой поддержки.

## Запас бюджета

147 822 ₽ из 180 000 ₽, остаток ~32 178 ₽ — на аксессуары стенда и резерв.

## Полный проект — 350 000 ₽

| № | Категория | Позиция | Цена | Магазин | Статус |
|:-:|:----------|:--------|:----:|:--------|:-------|
| | **ПК** | Сборка (9 компонентов) | 147 822 ₽ | DNS/Ozon | ⏳ |
| | **Стенд** | Orange Pi 5 Plus 16GB × 3 | 109 185 ₽ | НИКС | ⏳ |
| | | Аксессуары (БП, SD, кабели) | 4 000 ₽ | DNS/Ozon | ⏳ |
| | **Сеть** | MikroTik CSS326-24G-2S+RM | 18 199 ₽ | DNS Симферополь | ✅ Утверждён |
| | **Отладка** | DSLogic Plus | 9 927 ₽ | Ozon | ✅ Утверждён |
| | **Прочее** | Госпошлина Роспатент | 5 000 ₽ | Госуслуги | ✅ Утверждена |
| | | VPS reg.ru 12 мес. (C4-M4-D80) | 42 240 ₽ | reg.ru | ⏳ |
| | | Мелочи | 1 500 ₽ | — | ⏳ |
| | | **ИТОГО** | **337 873 ₽** | | |
| | | **Остаток** | **12 127 ₽** | | |
