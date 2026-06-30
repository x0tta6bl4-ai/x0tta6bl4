# Сборка рабочей станции — 180 000 ₽

Разработка систем защиты информации (компиляция ядра Linux, eBPF-программы, обучение ML-моделей)

## Компоненты

| № | Компонент | Модель | Цена | Ссылка для проверки |
|:-:|:----------|:-------|:----:|:--------------------|
| 1 | Процессор | AMD Ryzen 9 7950X (16 ядер / 32 потока) | 65 000 ₽ | https://www.dns-shop.ru/product/403a1d731bca3330/processor-amd-ryzen-9-7950x/ |
| 2 | Материнская плата | MSI PRO B650-S WIFI (AM5, DDR5) | 15 000 ₽ | https://www.dns-shop.ru/product/db73eff12d033330/materinskaa-plata-msi-pro-b650-s-wifi/ |
| 3 | Оперативная память | 64 GB (2×32 GB) DDR5-5200 | 18 000 ₽ | https://www.dns-shop.ru/search/?q=64+GB+DDR5+2%C3%9732 |
| 4 | SSD | 1 TB M.2 NVMe | 12 000 ₽ | https://www.dns-shop.ru/search/?q=SSD+1TB+NVMe |
| 5 | Блок питания | 750W (80+ Gold) | 10 000 ₽ | https://www.dns-shop.ru/search/?q=%D0%B1%D0%BB%D0%BE%D0%BA+%D0%BF%D0%B8%D1%82%D0%B0%D0%BD%D0%B8%D1%8F+750W+Gold |
| 6 | Корпус | ATX | 5 000 ₽ | https://www.dns-shop.ru/search/?q=%D0%BA%D0%BE%D1%80%D0%BF%D1%83%D1%81+ATX |
| 7 | Кулер CPU | Башенный | 5 000 ₽ | https://www.dns-shop.ru/search/?q=%D0%BA%D1%83%D0%BB%D0%B5%D1%80+CPU+%D0%B1%D0%B0%D1%88%D0%B5%D0%BD%D0%BD%D1%8B%D0%B9 |
| | **Подсборка** | | **130 000 ₽** | |
| 8 | Видеокарта (опционально, для ML) | RTX 4060 или аналогичная | 35 000 ₽ | https://www.dns-shop.ru/search/?q=RTX+4060 |
| | **ИТОГО с видеокартой** | | **~165 000 ₽** | |
| | **Запас на сборку/доставку** | | **~15 000 ₽** | |
| | **ВСЕГО** | | **~180 000 ₽** | |

## Чем заменить, если DNS нет

| Компонент | nix.ru | citilink.ru |
|:----------|:-------|:------------|
| Ryzen 9 7950X | https://www.nix.ru/autocatalog/autocatalog_amd/amd_ryzen_9_7950x.html | https://www.citilink.ru/search/?text=Ryzen+9+7950X |
| Сборка целиком | Готовый ПК в конфигураторе: https://www.nix.ru/computer/configurator.html | Готовые системные блоки: https://www.citilink.ru/catalog/sistemnye-bloki/ |

## Почему именно такой набор

| Компонент | Зачем |
|:----------|:------|
| Ryzen 9 7950X (16C/32T) | Компиляция ядра Linux использует все ядра. Сборка ядра на 4-ядерном ПК — 40+ минут, на 16-ядерном — 3-5 минут |
| 64 GB DDR5 | Компиляция eBPF-программ и обучение ML-моделей требуют много RAM. 32 GB будет упираться |
| SSD 1 TB NVMe | Скорость важна при работе с большими репозиториями (921 000 строк кода) |
| БП 750W | Стабильное питание при 100% нагрузке CPU |
| Видеокарта | Опционально — для обучения ML-моделей анализа аномалий сети |
