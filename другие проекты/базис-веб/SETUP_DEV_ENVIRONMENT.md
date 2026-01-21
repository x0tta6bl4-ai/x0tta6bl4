# 🔧 ПОЛНАЯ НАСТРОЙКА DEVELOPMENT ENVIRONMENT

**Версия:** 1.0  
**Дата:** 18 января 2026  
**Время на настройку:** 2-3 часа (полная)  
**Альтернатива:** 10 минут (через Docker)

---

## ⚡ БЫСТРЫЙ СТАРТ (10 мин с Docker)

```bash
# 1. Скачать этот репозиторий
git clone https://github.com/bazis/bazis-web-cad.git
cd bazis-web-cad

# 2. Запустить Docker Compose
docker-compose up -d

# 3. Проверить статус
docker ps
docker-compose logs

# 4. Открыть в браузере
open http://localhost:5173  # Frontend
open http://localhost:8000  # API docs (Swagger)
```

**Готово!** Можешь начинать разработку. 🚀

---

## 📋 РУЧНАЯ НАСТРОЙКА (для локальной разработки)

### Требования

```
✅ Node.js 20.10+ (или через nvm)
✅ Python 3.10+ (или через conda)
✅ Git 2.40+
✅ Docker & Docker Compose (опционально, но рекомендуется)
✅ 4+ GB RAM
✅ 2+ GB disk space
```

### Проверка требований

```bash
node --version      # v20.10.0+
npm --version       # 10.0.0+
python --version    # 3.10+
git --version       # 2.40+
docker --version    # 24.0+
docker-compose --version  # 2.20+
```

---

## 🎬 ШАГ 1: Инициализация Git репозитория

```bash
# Создать новый репозиторий
cd /path/to/bazis-web
git init
git remote add origin https://github.com/bazis/bazis-web-cad.git

# Или клонировать существующий
git clone https://github.com/bazis/bazis-web-cad.git bazis-web-cad
cd bazis-web-cad

# Создать ветку разработки
git checkout -b develop
git push -u origin develop
```

---

## 🎬 ШАГ 2: Frontend Setup (Node.js + Vite + React)

### 2.1 Установка зависимостей

```bash
# Перейти в frontend директорию
cd /path/to/bazis-web

# Очистить npm кеш (если проблемы)
npm cache clean --force

# Установить зависимости (это займёт 2-3 минуты)
npm install

# Проверка
npm list | head -20
```

### 2.2 Установка дополнительных пакетов для CAD

```bash
# Babylon.js экосистема (основной рендер)
npm install --save babylon@latest @babylonjs/core@latest @babylonjs/materials@latest @babylonjs/post-processes@latest @babylonjs/inspector@latest

# Параметрическое моделирование
npm install --save parametric-geometry opencascade.js

# Export форматы
npm install --save pdfkit dxf-writer three-step-exporter

# Оптимизация раскладки
npm install --save genetic-algorithm-js tinyqueue

# Состояние и синхронизация
npm install --save zustand nanoid

# Утилиты
npm install --save lodash-es date-fns uuid
```

### 2.3 Проверка конфигурации

```bash
# Проверить, что vite.config.ts скорректирован для Babylon.js
cat vite.config.ts | grep babylon

# Если нет, добавить оптимизацию
npm run config:babylon  # (опционально)
```

### 2.4 Запуск Dev Server

```bash
# Стартовать dev server (Vite)
npm run dev

# Вывод должен быть:
# ➜  Local:   http://localhost:5173/
# ➜  Press h to show help

# Открыть в браузере
open http://localhost:5173
```

✅ **Frontend готов!**

---

## 🎬 ШАГ 3: Backend Setup (Python + FastAPI + FreeCAD)

### 3.1 Создание Python виртуального окружения

```bash
# Перейти в backend директорию
cd services/backend

# Создать виртуальное окружение (venv)
python3 -m venv venv

# Активировать его
# На Mac/Linux:
source venv/bin/activate

# На Windows:
# .\venv\Scripts\activate

# Проверка (должна быть стрелка (venv))
# (venv) $ _
```

### 3.2 Установка зависимостей Python

```bash
# Убедиться, что виртуальное окружение активно
which python  # Должна быть строка с venv

# Обновить pip
pip install --upgrade pip setuptools wheel

# Установить основные зависимости
pip install fastapi uvicorn pydantic python-multipart cors

# Установить CAD/Моделирование
pip install FreeCAD cadquery opencascade

# Установить ML/Optimization
pip install numpy scipy scikit-learn tensorflow torch

# Установить базы данных
pip install psycopg2-binary pymongo sqlalchemy alembic

# Установить утилиты
pip install python-dotenv requests websockets

# Установить dev инструменты
pip install pytest pytest-cov black flake8 mypy
```

Проверка:
```bash
pip list | grep -E "fastapi|FreeCAD|tensorflow"
```

### 3.3 Структура backend файлов

```
services/backend/
├── venv/                      # Виртуальное окружение (создано выше)
├── app/
│   ├── __init__.py
│   ├── main.py               # Главная FastAPI app
│   ├── models.py             # Pydantic модели
│   ├── database.py           # PostgreSQL/MongoDB подключение
│   ├── routers/
│   │   ├── cabinet.py        # /api/cabinet/* routes
│   │   ├── materials.py      # /api/materials/* routes
│   │   ├── nesting.py        # /api/nesting/* routes
│   │   └── export.py         # /api/export/* routes
│   └── services/
│       ├── cabinet_modeler.py    # CabinetModeler класс
│       ├── nesting_optimizer.py  # NestingOptimizer класс
│       └── export_service.py     # ExportService класс
├── tests/
│   ├── test_cabinet.py
│   ├── test_nesting.py
│   └── test_api.py
├── requirements.txt          # Список зависимостей
├── .env.example             # Пример переменных окружения
├── main.py                  # Точка входа (python main.py)
└── run.sh                   # Скрипт запуска
```

### 3.4 Создание основного файла app/main.py

```bash
# Создать основную структуру
mkdir -p services/backend/app/routers
mkdir -p services/backend/app/services
mkdir -p services/backend/tests
```

### 3.5 Запуск FastAPI сервера

```bash
# Убедиться, что виртуальное окружение активно
# (venv) $ _

# Запустить сервер
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Вывод:
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Application startup complete
# INFO:     Watching for file changes in ...

# Открыть в браузере
open http://localhost:8000/docs  # Swagger UI
```

✅ **Backend готов!**

---

## 🎬 ШАГ 4: Database Setup

### 4.1 PostgreSQL (структурированные данные)

```bash
# Вариант 1: Использовать Docker (рекомендуется)
docker run -d \
  --name bazis-postgres \
  -e POSTGRES_USER=bazis \
  -e POSTGRES_PASSWORD=secure_password_here \
  -e POSTGRES_DB=bazis_cad \
  -p 5432:5432 \
  postgres:15-alpine

# Проверка
docker ps | grep postgres

# Вариант 2: Установить локально (Mac)
brew install postgresql@15
brew services start postgresql@15
createdb bazis_cad

# Вариант 3: Установить локально (Ubuntu)
sudo apt-get install postgresql postgresql-contrib
sudo -u postgres createdb bazis_cad
```

Проверка подключения:
```bash
# Используя psql
psql -U bazis -d bazis_cad -h localhost

# Вывод: bazis_cad=#
# Выход: \q
```

### 4.2 MongoDB (документы и история)

```bash
# Вариант 1: Docker (рекомендуется)
docker run -d \
  --name bazis-mongo \
  -e MONGO_INITDB_ROOT_USERNAME=bazis \
  -e MONGO_INITDB_ROOT_PASSWORD=secure_password_here \
  -p 27017:27017 \
  mongo:latest

# Проверка
docker ps | grep mongo

# Вариант 2: Локально (Mac)
brew tap mongodb/brew
brew install mongodb-community
brew services start mongodb-community

# Вариант 3: Локально (Ubuntu)
sudo apt-get install -y mongodb
sudo systemctl start mongodb
```

Проверка подключения:
```bash
# Используя mongo shell
mongosh mongodb://bazis:secure_password_here@localhost:27017/bazis_cad

# Вывод: bazis_cad>
# Выход: exit
```

### 4.3 Redis (кеширование и очереди)

```bash
# Docker (рекомендуется)
docker run -d \
  --name bazis-redis \
  -p 6379:6379 \
  redis:latest

# Локально (Mac)
brew install redis
brew services start redis

# Локально (Ubuntu)
sudo apt-get install redis-server
sudo systemctl start redis-server

# Проверка
redis-cli ping
# Вывод: PONG
```

### 4.4 Инициализация schema

```bash
# В backend виртуальном окружении
cd services/backend

# Создать миграции (используя Alembic)
alembic init migrations

# Создать первую миграцию
alembic revision --autogenerate -m "Initial schema"

# Применить миграции
alembic upgrade head

# Проверить schema
psql -U bazis -d bazis_cad -c "\dt"
```

✅ **Database готовы!**

---

## 🎬 ШАГ 5: Environment Variables

### 5.1 Создать .env файлы

```bash
# Frontend (.env в корне проекта)
cat > .env << 'EOF'
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_ENV=development
VITE_DEBUG=true
EOF

# Backend (services/backend/.env)
cat > services/backend/.env << 'EOF'
# FastAPI
FASTAPI_ENV=development
DEBUG=true
SECRET_KEY=your-secret-key-here-change-in-production

# Database
POSTGRES_USER=bazis
POSTGRES_PASSWORD=secure_password_here
POSTGRES_DB=bazis_cad
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# MongoDB
MONGO_URI=mongodb://bazis:secure_password_here@localhost:27017/bazis_cad

# Redis
REDIS_URL=redis://localhost:6379/0

# AI/ML
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen:32b
GEMINI_API_KEY=your-gemini-key-here

# Paths
CAD_EXPORT_PATH=/tmp/bazis-exports
CAD_CACHE_PATH=/tmp/bazis-cache
EOF
```

✅ **Environment готовы!**

---

## 🎬 ШАГ 6: Ollama Setup (опционально, для AI анализа)

### 6.1 Установка Ollama

```bash
# На Mac
brew install ollama

# На Linux
curl https://ollama.ai/install.sh | sh

# На Windows
# Скачать с https://ollama.ai/download
```

### 6.2 Запуск Ollama сервера

```bash
# Запустить сервер (будет слушать на http://localhost:11434)
ollama serve

# В другом терминале:
# Скачать модели (это займёт 5-10 минут)
ollama pull qwen:32b
ollama pull mistral:latest

# Проверка
curl http://localhost:11434/api/tags
```

✅ **Ollama готова!**

---

## 🎬 ШАГ 7: Проверка всех сервисов

### Checklist

```bash
# ✅ Frontend (Vite)
curl http://localhost:5173 -I
# HTTP/1.1 200 OK

# ✅ Backend (FastAPI)
curl http://localhost:8000/docs -I
# HTTP/1.1 200 OK

# ✅ PostgreSQL
psql -U bazis -d bazis_cad -c "SELECT 1;"
# Output: 1

# ✅ MongoDB
mongosh --eval "db.runCommand({ping: 1})" mongodb://bazis:...@localhost:27017/bazis_cad
# Output: { ok: 1 }

# ✅ Redis
redis-cli ping
# Output: PONG

# ✅ Ollama
curl http://localhost:11434/api/tags
# Output: {"models": [...]}
```

Все 6 сервисов должны ответить ✅

---

## 📊 ПРОВЕРКА ВСЕГО ЧЕРЕЗ DOCKER COMPOSE

Если не хочешь настраивать вручную, используй Docker:

```bash
# В корне проекта
docker-compose up -d

# Проверить логи
docker-compose logs -f

# Остановить
docker-compose down

# Очистить всё
docker-compose down -v
```

---

## 📚 СТРУКТУРА ПРОЕКТА (ИТОГОВАЯ)

```
bazis-web-cad/
├── src/                          # Frontend (React)
│   ├── components/               # React компоненты
│   ├── services/                 # API сервисы
│   ├── store/                    # Zustand store
│   ├── types.ts                  # TypeScript типы
│   ├── App.tsx                   # Главный компонент
│   └── index.tsx                 # Точка входа
│
├── services/
│   └── backend/                  # Backend (Python)
│       ├── app/
│       │   ├── main.py           # FastAPI app
│       │   ├── models.py         # Pydantic модели
│       │   ├── database.py       # DB подключение
│       │   ├── routers/          # API routes
│       │   └── services/         # Бизнес логика
│       ├── migrations/           # Alembic миграции
│       ├── tests/                # Pytest тесты
│       ├── venv/                 # Виртуальное окружение
│       ├── requirements.txt      # Python зависимости
│       ├── .env                  # Переменные окружения
│       └── main.py               # Точка входа
│
├── docker-compose.yml            # Docker Compose (all services)
├── docker-compose.dev.yml        # Development версия
├── docker-compose.prod.yml       # Production версия
│
├── package.json                  # NPM зависимости
├── tsconfig.json                 # TypeScript конфигурация
├── vite.config.ts                # Vite конфигурация
├── .env                          # Frontend env vars
│
├── README.md                     # Общее описание
├── SETUP_DEV_ENVIRONMENT.md      # Этот файл
└── docs/                         # Документация
    ├── API.md                    # API документация
    ├── ARCHITECTURE.md           # Архитектура
    └── CONTRIBUTING.md           # Как контрибьютить
```

---

## 🔧 ПОЛЕЗНЫЕ КОМАНДЫ

### Frontend

```bash
# Стартовать dev server
npm run dev

# Собрать production сборку
npm run build

# Превью production сборки
npm run preview

# Линтинг (проверка кода)
npm run lint

# Форматирование кода
npm run format
```

### Backend

```bash
# Стартовать dev server
cd services/backend
source venv/bin/activate
uvicorn app.main:app --reload

# Запустить тесты
pytest -v

# Проверка типов
mypy app/

# Линтинг
flake8 app/

# Форматирование
black app/
```

### Database

```bash
# Создать новую миграцию
alembic revision --autogenerate -m "Description"

# Применить миграции
alembic upgrade head

# Откатить миграцию
alembic downgrade -1

# Экспортировать данные (PostgreSQL)
pg_dump bazis_cad > backup.sql

# Импортировать данные
psql bazis_cad < backup.sql
```

### Docker

```bash
# Стартовать все сервисы
docker-compose up -d

# Логи конкретного сервиса
docker-compose logs -f postgres

# Остановить всё
docker-compose down

# Очистить всё (включая данные!)
docker-compose down -v

# Перестартовать сервис
docker-compose restart postgres
```

---

## 🆘 TROUBLESHOOTING

### "port 5173 is already in use"
```bash
# Найти процесс на порте
lsof -i :5173

# Убить процесс
kill -9 <PID>

# Или используй другой порт
npm run dev -- --port 3000
```

### "ModuleNotFoundError: No module named 'fastapi'"
```bash
# Убедиться, что виртуальное окружение активно
which python  # Должна быть строка с venv

# Переактивировать
source venv/bin/activate
pip install -r requirements.txt
```

### "Cannot connect to database"
```bash
# Проверить, что PostgreSQL запущен
docker ps | grep postgres

# Или на Mac
brew services list | grep postgresql

# Если не запущен, стартовать
docker-compose up -d postgres
```

### "Ollama timeout"
```bash
# Убедиться, что Ollama запущен
curl http://localhost:11434/api/tags

# Если не отвечает, стартовать в новом терминале
ollama serve

# Если модель не скачана
ollama pull qwen:32b
```

---

## ✅ ПРОВЕРКА УСПЕШНОЙ НАСТРОЙКИ

Все эти команды должны работать:

```bash
# Терминал 1: Frontend
cd bazis-web-cad
npm run dev
# ➜  Local:   http://localhost:5173/

# Терминал 2: Backend (из services/backend)
source venv/bin/activate
uvicorn app.main:app --reload
# INFO:     Uvicorn running on http://0.0.0.0:8000

# Терминал 3: Ollama (опционально)
ollama serve
# Listening on 127.0.0.1:11434

# Терминал 4: Проверка
curl http://localhost:5173        # Frontend ✅
curl http://localhost:8000/docs   # API ✅
psql -U bazis -d bazis_cad        # DB ✅
redis-cli ping                    # Redis ✅
mongosh <uri>                     # MongoDB ✅
curl http://localhost:11434/api/tags  # Ollama ✅
```

Если все 6+ сервисов отвечают ✅, то ты готов к разработке!

---

## 📞 СЛЕДУЮЩИЙ ШАГ

Прочитай [TEAM_ASSIGNMENTS.md](./TEAM_ASSIGNMENTS.md) для распределения задач между разработчиками.

Или начни с [QUICK_START_DAY1_CHECKLIST.md](./QUICK_START_DAY1_CHECKLIST.md) для первых шагов.

---

**Успехи в разработке! 🚀**

Дата: 18.01.2026  
Версия: 1.0  
Статус: ✅ READY
