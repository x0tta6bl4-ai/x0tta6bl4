# Сборка рабочей станции — ~179 510 ₽

Разработка систем защиты информации (компиляция ядра Linux, eBPF-программы, обучение ML-моделей)

## Спецификация

| № | Компонент | Модель | Характеристики | Цена | Ссылка |
|:-:|:----------|:-------|:--------------|:----:|:-------|
| 1 | **Процессор** | AMD Ryzen 9 9900X OEM | 12 ядер / 24 потока, 4.4-5.6 ГГц, TDP 120 Вт | 29 940 ₽ | https://www.compday.ru/komplektuyuszie/protsessory/482775.htm |
| 2 | **Материнская плата** | MSI PRO B650-P WIFI | ATX, AM5, B650, 4×DDR5, Wi-Fi 6E | 11 300 ₽ | https://www.citilink.ru/product/materinskaya-plata-msi-pro-b650-p-wifi-socket-am5-amd-b650-4xddr5-atx-2144774/ |
| 3 | **ОЗУ** | KingSpec KS4800D5N11032G DDR5 (2 шт.) | 64 ГБ (2×32), 4800 МГц | 31 980 ₽ | https://www.citilink.ru/catalog/moduli-pamyati--ddr5/ |
| 4 | **Видеокарта** | Palit GeForce RTX 4070 Super Dual 12GB | 12 ГБ GDDR6X, 192 бит | 74 950 ₽ | https://hardprice.ru/658917-videokarta-palit-geforce-rtx-4070-super-dual-oc-12gb-ned407ss19k9-1043d |
| 5 | **SSD** | KINGSPEC NX 1TB | 1 ТБ, M.2, NVMe PCIe 3.0 | 12 990 ₽ | https://www.citilink.ru/catalog/ssd-nakopiteli--m-2/ |
| 6 | **Кулер CPU** | ID-COOLING SE-207-XT Slim | 2-секционный, 120мм, 220 Вт | 2 730 ₽ | https://www.citilink.ru/product/ustroistvo-ohlazhdeniya-kuler-id-cooling-se-207-xt-slim-120mm-ret-1879798/ |
| 7 | **Блок питания** | DeepCool PN750M V2 Gen.5 | 750 Вт, 80+ Gold, ATX 3.0 | 7 480 ₽ | https://www.citilink.ru/catalog/bloki-pitaniya--bloki-pitanija-750-vt/ |
| 8 | **Корпус** | Montech XR Wood White | ATX, стекло | 5 540 ₽ | https://www.citilink.ru/catalog/korpusa/MONTECH/ |
| 9 | **Сетевая карта** | Intel i225-V (дискретная, PCIe) | 2.5GbE, нативный XDP/eBPF, драйвер igc, zero-copy AF_XDP | 2 600 ₽ | Ozon: поиск "Intel i225-V PCIe" |
| | | | **ИТОГО** | **~179 510 ₽** | |

## Почему Intel i225-V

eBPF/XDP программы обрабатывают пакеты до того как они попадают в сетевой стек ядра. Для корректных замеров задержек и пропускной способности нужна сетевая карта с:

- **Нативной поддержкой AF_XDP (zero-copy)** — драйвер `igc` поддерживает это полностью
- **Аппаратным RSS** — равномерное распределение пакетов по ядрам CPU
- **Драйвером из основного ядра Linux** — не требует проприетарных прошивок

Средняя задержка обработки кадров на Intel i225-V с XDP: ~11 микросекунд.

Встроенные сетевые карты на материнских платах (Realtek) не имеют полной поддержки AF_XDP zero-copy.

## Почему Ryzen 9 9900X вместо 7950X

- 9900X: 12 ядер / 24 потока, 29 940 ₽
- 7950X: 16 ядер / 32 потока, ~65 000 ₽

Разница в цене — 35 000 ₽. Разница в скорости компиляции — ~20%. Для разработки 12 ядер более чем достаточно. Сэкономленные деньги ушли на видеокарту RTX 4070 для ML-моделей и сетевую карту Intel.

## Запас бюджета

179 510 ₽ из 180 000 ₽. Остаток 490 ₽ — на кабели и термопасту.

На каждую позицию нужен чек с QR-кодом после получения средств. Сборка — самостоятельно из комплектующих (допускается правилами соцконтракта).
