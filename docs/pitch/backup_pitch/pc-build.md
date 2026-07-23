# Сборка рабочей станции — 142 539 ₽

Разработка систем защиты информации (компиляция ядра Linux, обработка сетевых пакетов, ML-модели CUDA)

## Спецификация (финальная)

| № | Компонент | Модель | Характеристики | Цена | Магазин | Ссылка |
|:-:|:----------|:-------|:--------------|:----:|:--------|:-------|
| 1 | **Процессор** | AMD Ryzen 9 9900X Tray | 12 ядер / 24 потока, 4.4-5.6 ГГц, TDP 120 Вт | 32 850 ₽ | Komtek | [komtek.net.ru](https://komtek.net.ru/index.php?route=product/search&search=9900X) |
| 2 | **Материнская плата** | MSI PRO B650-P WIFI | ATX, AM5, B650, 4×DDR5, Wi-Fi 6E, 2.5GbE | 11 120 ₽ | Komtek | [komtek.net.ru](https://komtek.net.ru/index.php?route=product/search&search=MSI+PRO+B650-P+WIFI) |
| 3 | **ОЗУ** | Crucial 32GB DDR5-5600 (CT32G56C46U5) | 32 ГБ, DDR5-5600 | 37 600 ₽ | Komtek | [komtek.net.ru](https://komtek.net.ru/index.php?route=product/search&search=CT32G56C46U5) |
| 4 | **SSD** | ADATA XPG GAMMIX S60 1TB PCIe 4.0 | 1 ТБ, M.2 NVMe PCIe 4.0 | 11 610 ₽ | Komtek | [komtek.net.ru](https://komtek.net.ru/index.php?route=product/search&search=ADATA+XPG+GAMMIX+S60+1TB) |
| 5 | **Видеокарта** | Gigabyte RTX 4060 Gaming OC 8GB | 8 ГБ GDDR6, CUDA 3072 ядра | 33 230 ₽ | Komtek | [komtek.net.ru](https://komtek.net.ru/index.php?route=product/search&search=GV-N4060GAMING+OC-8GD) |
| 6 | **Блок питания** | DeepCool PQ750G (GamerStorm) | 750 Вт, ATX 3.1, 80+ Gold, модульный, японские конденсаторы | 7 310 ₽ | Komtek | [komtek.net.ru](https://komtek.net.ru/index.php?route=product/search&search=PQ750G) |
| 7 | **Кулер CPU** | ID-Cooling SE-207-XT SLIM | 2-секционный, 120мм, 220 Вт TDP, 135 мм высота | 2 720 ₽ | Komtek | [komtek.net.ru](https://komtek.net.ru/index.php?route=product/search&search=SE-207-XT) |
| 8 | **Корпус** | 1STPLAYER TRILOBITE T7-P Black | Midi Tower ATX, GPU до 340 мм, кулер до 185 мм | 4 220 ₽ | Komtek | [komtek.net.ru](https://komtek.net.ru/index.php?route=product/search&search=TRILOBITE+T7-P) |
| 9 | **Сетевая карта** | ORIENT XWT-INT226PE (Intel I226-V) | 2.5GbE PCIe, драйвер igc, AF_XDP zero-copy | 1 879 ₽ | Ozon | [Ozon](https://ozon.ru/search/?text=ORIENT+XWT-INT226PE) |
| | | | **ИТОГО ПК** | **142 539 ₽** | | |

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

Обработчики сетевых пакетов в Linux работают до попадания трафика в обычный стек ядра. Intel I226-V — улучшенная версия I225-V (исправлены баги ранних степпингов). Драйвер `igc` поддерживает аппаратное ускорение обработки пакетов. Встроенные Realtek на материнских платах не имеют этой поддержки.

## Место в бюджете проекта
 
Рабочая станция — 142 539 ₽ из общей сметы проекта 350 000 ₽ (см. таблицу ниже).
 
## Полный проект — 350 000 ₽
 
| № | Категория | Позиция | Цена | Магазин | Статус |
|:-:|:----------|:--------|:----:|:--------|:-------|
| | **ПК** | Сборка (9 компонентов) | 142 539 ₽ | Komtek/Ozon | ⏳ |
| | **Стенд** | Orange Pi 5 Plus 16GB × 3 | 109 185 ₽ | НИКС | ⏳ |
| | | Карта памяти MicroSDXC 64GB (3 шт.) | 3 210 ₽ | Komtek | ⏳ |
| | | СЗУ HOCO N32 Glory USB-C (3 шт.) | 2 325 ₽ | Komtek | ⏳ |
| | | Сетевой кабель патч-корд Cat.5e (5 шт.) | 1 001 ₽ | DNS | ⏳ |
| | | Сетевой фильтр Pilot PRO v23 3м | 3 899 ₽ | DNS | ⏳ |
| | | Внешний карт-ридер DEXP JET-01 | 850 ₽ | DNS | ⏳ |
| | | Набор отверток Xiaomi Mi x Wiha | 1 999 ₽ | DNS | ⏳ |
| | | Маршрутизатор MikroTik hAP lite | 3 500 ₽ | DNS | ⏳ |
| | | Разветвитель USB DEXP BT7-01 (активный)| 2 700 ₽ | DNS | ⏳ |
| | | Кабель HDMI DEXP 1.8м (3 шт.) | 1 863 ₽ | DNS | ⏳ |
| | **Сеть** | MikroTik CSS326-24G-2S+RM | 18 199 ₽ | DNS Симферополь | ✅ Утверждён |
| | **Отладка** | DSLogic Plus | 9 927 ₽ | Ozon | ✅ Утверждён |
| | **Прочее** | Госпошлина Роспатент | 5 000 ₽ | Госуслуги | ✅ Утверждена |
| | | VPS reg.ru 12 мес. (HP C6-M6-D100) | 43 803 ₽ | reg.ru | ⏳ |
| | | **ИТОГО** | **350 000 ₽** | | |
| | | **Остаток** | **0 ₽** | | |
