"""
Улучшенные техники мышления для x0tta6bl4

Интегрирует найденные техники мышления и мозгового штурма:
- Six Thinking Hats
- First Principles Thinking
- Lateral Thinking
- Mind Maps
- Обратное планирование
- "Думай вслух"
- Метод "Трёх вопросов"
- Фрейминг
- Саморефлексия
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ThinkingHat(Enum):
    """Шесть шляп мышления де Боно"""

    WHITE = "white"  # Факты и информация
    RED = "red"  # Эмоции и чувства
    BLACK = "black"  # Критика и осторожность
    YELLOW = "yellow"  # Оптимизм и преимущества
    GREEN = "green"  # Креативность и новые идеи
    BLUE = "blue"  # Управление процессом


@dataclass
class HatAnalysis:
    """Анализ с использованием Six Thinking Hats"""

    white: dict[str, Any] = field(default_factory=dict)  # Факты
    red: dict[str, Any] = field(default_factory=dict)  # Эмоции
    black: dict[str, Any] = field(default_factory=dict)  # Риски
    yellow: dict[str, Any] = field(default_factory=dict)  # Преимущества
    green: dict[str, Any] = field(default_factory=dict)  # Креативные идеи
    blue: dict[str, Any] = field(default_factory=dict)  # Процесс


@dataclass
class FirstPrinciplesDecomposition:
    """Разложение на первые принципы"""

    fundamentals: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    core_truths: list[str] = field(default_factory=list)


@dataclass
class LateralThinkingApproach:
    """Латеральное мышление"""

    standard_approach: str
    alternative_approaches: list[str] = field(default_factory=list)
    reversed_problem: str | None = None
    random_stimulation: str | None = None
    provocation: str | None = None


@dataclass
class ThreeQuestionsReflection:
    """Метод трёх вопросов"""

    what_worked: list[str] = field(default_factory=list)
    what_improve: list[str] = field(default_factory=list)
    what_learn: list[str] = field(default_factory=list)


class SixThinkingHats:
    """Реализация техники Six Thinking Hats"""

    def analyze(self, task: dict[str, Any]) -> HatAnalysis:
        """
        Анализ задачи с использованием всех шести шляп.

        Args:
            task: Описание задачи

        Returns:
            HatAnalysis с результатами анализа
        """
        analysis = HatAnalysis()

        # Белая шляпа: Факты
        analysis.white = {
            "facts": self._gather_facts(task),
            "data": self._collect_data(task),
            "information": self._get_information(task),
        }

        # Красная шляпа: Эмоции
        analysis.red = {
            "feelings": self._identify_feelings(task),
            "intuition": self._get_intuition(task),
            "emotions": self._assess_emotions(task),
        }

        # Чёрная шляпа: Критика
        analysis.black = {
            "risks": self._identify_risks(task),
            "problems": self._find_problems(task),
            "cautions": self._get_cautions(task),
        }

        # Жёлтая шляпа: Оптимизм
        analysis.yellow = {
            "benefits": self._identify_benefits(task),
            "advantages": self._find_advantages(task),
            "opportunities": self._discover_opportunities(task),
        }

        # Зелёная шляпа: Креативность
        analysis.green = {
            "creative_ideas": self._generate_creative_ideas(task),
            "alternatives": self._find_alternatives(task),
            "innovations": self._suggest_innovations(task),
        }

        # Синяя шляпа: Управление
        control = self._control_thinking(analysis)
        analysis.blue = {
            "process": self._manage_process(analysis),
            "next_steps": self._define_next_steps(analysis),
            "control": control,
            # Backward-compatible shortcut used by unit tests and consumers.
            "quality": control.get("quality"),
        }

        return analysis

    def _gather_facts(self, task: dict[str, Any]) -> list[str]:
        """Сбор фактов (белая шляпа)"""
        facts = []
        if "type" in task:
            facts.append(f"Тип задачи: {task['type']}")
        if "description" in task:
            facts.append(f"Описание: {task['description']}")
        if "complexity" in task:
            facts.append(f"Сложность: {task['complexity']}")
        return facts

    def _collect_data(self, task: dict[str, Any]) -> dict[str, Any]:
        """Сбор данных"""
        return task.get("data", {})

    def _get_information(self, task: dict[str, Any]) -> list[str]:
        """Получение информации"""
        return task.get("info", [])

    def _identify_feelings(self, task: dict[str, Any]) -> list[str]:
        """Идентификация чувств (красная шляпа)"""
        # Упрощенная реализация
        return ["Уверенность в решении", "Осторожность при выполнении"]

    def _get_intuition(self, task: dict[str, Any]) -> str:
        """Получение интуиции"""
        return "Интуиция подсказывает, что задача решаема"

    def _assess_emotions(self, task: dict[str, Any]) -> dict[str, float]:
        """Оценка эмоций"""
        return {"confidence": 0.8, "caution": 0.2}

    def _identify_risks(self, task: dict[str, Any]) -> list[str]:
        """Идентификация рисков (чёрная шляпа)"""
        risks = []
        complexity = task.get("complexity", 0.5)
        if complexity > 0.7:
            risks.append("Высокая сложность может привести к ошибкам")
        if "deadline" in task:
            risks.append("Ограниченное время может повлиять на качество")
        return risks

    def _find_problems(self, task: dict[str, Any]) -> list[str]:
        """Поиск проблем"""
        return ["Потенциальные проблемы требуют внимания"]

    def _get_cautions(self, task: dict[str, Any]) -> list[str]:
        """Получение предостережений"""
        return ["Требуется тщательная проверка"]

    def _identify_benefits(self, task: dict[str, Any]) -> list[str]:
        """Идентификация преимуществ (жёлтая шляпа)"""
        return [
            "Улучшение системы мышления",
            "Повышение эффективности",
            "Накопление знаний",
        ]

    def _find_advantages(self, task: dict[str, Any]) -> list[str]:
        """Поиск преимуществ"""
        return [
            "Использование проверенных техник",
            "Интеграция с существующими методами",
        ]

    def _discover_opportunities(self, task: dict[str, Any]) -> list[str]:
        """Обнаружение возможностей"""
        return ["Возможность улучшить систему", "Шанс создать инновацию"]

    def _generate_creative_ideas(self, task: dict[str, Any]) -> list[str]:
        """Генерация креативных идей (зелёная шляпа)"""
        return [
            "Комбинировать несколько техник",
            "Использовать нестандартные подходы",
            "Применить латеральное мышление",
        ]

    def _find_alternatives(self, task: dict[str, Any]) -> list[str]:
        """Поиск альтернатив"""
        return ["Альтернативный подход 1", "Альтернативный подход 2"]

    def _suggest_innovations(self, task: dict[str, Any]) -> list[str]:
        """Предложение инноваций"""
        return ["Инновация 1", "Инновация 2"]

    def _manage_process(self, analysis: HatAnalysis) -> dict[str, Any]:
        """Управление процессом (синяя шляпа)"""
        return {
            "summary": "Анализ завершен с использованием всех шляп",
            "recommendation": "Использовать комбинированный подход",
            "next_hat": "green",  # Следующая шляпа для углубления
        }

    def _define_next_steps(self, analysis: HatAnalysis) -> list[str]:
        """Определение следующих шагов"""
        return [
            "Применить креативные идеи",
            "Учесть риски",
            "Использовать преимущества",
        ]

    def _control_thinking(self, analysis: HatAnalysis) -> dict[str, Any]:
        """Контроль процесса мышления"""
        return {"status": "controlled", "focus": "balanced_analysis", "quality": "high"}


class FirstPrinciplesThinking:
    """Реализация First Principles Thinking"""

    def decompose(self, problem: dict[str, Any]) -> FirstPrinciplesDecomposition:
        """
        Разложение проблемы на первые принципы.

        Args:
            problem: Описание проблемы

        Returns:
            FirstPrinciplesDecomposition
        """
        decomposition = FirstPrinciplesDecomposition()

        # Выделяем фундаментальные элементы
        decomposition.fundamentals = self._extract_fundamentals(problem)

        # Идентифицируем предположения
        decomposition.assumptions = self._identify_assumptions(problem)

        # Находим основные истины
        decomposition.core_truths = self._find_core_truths(problem)

        return decomposition

    def _extract_fundamentals(self, problem: dict[str, Any]) -> list[str]:
        """Извлечение фундаментальных элементов"""
        fundamentals = []

        # Разбиваем проблему на базовые компоненты
        if "type" in problem:
            fundamentals.append(f"Тип: {problem['type']}")
        if "goal" in problem:
            fundamentals.append(f"Цель: {problem['goal']}")
        if "constraints" in problem:
            fundamentals.append(f"Ограничения: {problem['constraints']}")

        return fundamentals

    def _identify_assumptions(self, problem: dict[str, Any]) -> list[str]:
        """Идентификация предположений"""
        assumptions = []

        # Проверяем скрытые предположения
        if "complexity" in problem:
            assumptions.append(f"Предположение о сложности: {problem['complexity']}")
        if "deadline" in problem:
            assumptions.append(f"Предположение о времени: {problem['deadline']}")

        return assumptions

    def _find_core_truths(self, problem: dict[str, Any]) -> list[str]:
        """Поиск основных истин"""
        return [
            "Проблема требует решения",
            "Существуют ограничения",
            "Есть цель для достижения",
        ]

    def build_from_scratch(
        self, decomposition: FirstPrinciplesDecomposition
    ) -> dict[str, Any]:
        """
        Построение решения с нуля на основе первых принципов.

        Args:
            decomposition: Разложение на первые принципы

        Returns:
            Решение, построенное с нуля
        """
        solution = {
            "fundamentals": decomposition.fundamentals,
            "assumptions_validated": decomposition.assumptions,
            "core_truths_applied": decomposition.core_truths,
            "built_from_scratch": True,
        }

        return solution


class LateralThinking:
    """Реализация латерального мышления"""

    def generate(self, problem: dict[str, Any]) -> LateralThinkingApproach:
        """
        Генерация нестандартных подходов.

        Args:
            problem: Описание проблемы

        Returns:
            LateralThinkingApproach
        """
        approach = LateralThinkingApproach(
            standard_approach=self._get_standard_approach(problem)
        )

        # Альтернативные подходы
        approach.alternative_approaches = self._find_alternatives(problem)

        # Обращение проблемы
        approach.reversed_problem = self._reverse_problem(problem)

        # Случайная стимуляция
        approach.random_stimulation = self._random_stimulation(problem)

        # Провокация
        approach.provocation = self._provocation(problem)

        return approach

    def _get_standard_approach(self, problem: dict[str, Any]) -> str:
        """Получение стандартного подхода"""
        return f"Стандартный подход для {problem.get('type', 'задачи')}"

    def _find_alternatives(self, problem: dict[str, Any]) -> list[str]:
        """Поиск альтернативных подходов"""
        return [
            "Подход с противоположной стороны",
            "Подход через аналогию",
            "Подход через комбинацию",
        ]

    def _reverse_problem(self, problem: dict[str, Any]) -> str:
        """Обращение проблемы"""
        return f"Обратная проблема: вместо решения {problem.get('type', 'X')}, решить противоположное"

    def _random_stimulation(self, problem: dict[str, Any]) -> str:
        """Случайная стимуляция"""
        random_words = ["облако", "мост", "ключ", "зеркало"]
        return f"Случайная стимуляция: {random_words[0]} → как это связано с проблемой?"

    def _provocation(self, problem: dict[str, Any]) -> str:
        """Провокация"""
        return f"Провокация: что если {problem.get('type', 'проблема')} на самом деле не проблема?"


class ReversePlanner:
    """Реализация обратного планирования"""

    def plan(self, goal: str, max_steps: int = 8) -> list[str]:
        """
        Планирование от цели к началу.

        Args:
            goal: Конечная цель
            max_steps: Защита от зацикливания при неизвестной формулировке цели

        Returns:
            План в обратном порядке (от цели к началу)
        """
        plan = [goal]

        # Двигаемся назад от цели
        current = goal
        seen = {current}
        for _ in range(max(1, max_steps)):
            if self._is_start_state(current):
                break
            previous = self._find_previous_step(current)
            if previous in seen:
                if not self._is_start_state(previous):
                    previous = "Начальное состояние"
                plan.append(previous)
                break
            plan.append(previous)
            seen.add(previous)
            current = previous

        return plan

    def _is_start_state(self, state: str) -> bool:
        """Проверка, является ли состояние начальным"""
        lower = state.lower()
        return (
            "начало" in lower
            or "начальн" in lower
            or "start" in lower
            or "initial" in lower
        )

    def _find_previous_step(self, current: str) -> str:
        """Поиск предыдущего шага"""
        # Упрощенная реализация
        if "цель" in current.lower() or "goal" in current.lower():
            return "Оптимизация процессов"
        elif "оптимизация" in current.lower():
            return "Идентификация узких мест"
        elif "идентификация" in current.lower():
            return "Мониторинг текущего состояния"
        else:
            return "Начальное состояние"


class ThinkAloudLogger:
    """Реализация техники "Думай вслух" """

    def __init__(self):
        self.thoughts: list[dict[str, Any]] = []

    def log(self, thought: str, context: dict[str, Any] | None = None):
        """
        Логирование мысли вслух.

        Args:
            thought: Мысль для логирования
            context: Контекст мысли
        """
        entry = {"thought": thought, "timestamp": time.time(), "context": context or {}}
        self.thoughts.append(entry)
        logger.info(f"💭 Думаю вслух: {thought}")

    def get_thoughts(self) -> list[dict[str, Any]]:
        """Получение всех мыслей"""
        return self.thoughts

    def detect_logic_gaps(self) -> list[str]:
        """Обнаружение пробелов в логике"""
        gaps = []

        # Простая проверка на пробелы
        for i, thought in enumerate(self.thoughts):
            if i > 0:
                prev_thought = self.thoughts[i - 1]
                # Проверяем логическую связь
                if not self._is_logically_connected(prev_thought, thought):
                    gaps.append(
                        f"Пробел между '{prev_thought['thought']}' и '{thought['thought']}'"
                    )

        return gaps

    def _is_logically_connected(
        self, thought1: dict[str, Any], thought2: dict[str, Any]
    ) -> bool:
        """Проверка логической связи между мыслями"""
        # Упрощенная проверка
        return True  # В реальной реализации - более сложная логика


class ThreeQuestionsReflection:
    """Реализация метода трёх вопросов"""

    def reflect(self, result: dict[str, Any]) -> ThreeQuestionsReflection:
        """
        Рефлексия с использованием трёх вопросов.

        Args:
            result: Результат выполнения

        Returns:
            ThreeQuestionsReflection
        """
        reflection = ThreeQuestionsReflection()

        # Что было удачным?
        reflection.what_worked = self._extract_successes(result)

        # Что можно улучшить?
        reflection.what_improve = self._identify_improvements(result)

        # Какие выводы для будущего?
        reflection.what_learn = self._extract_lessons(result)

        return reflection

    def _extract_successes(self, result: dict[str, Any]) -> list[str]:
        """Извлечение успехов"""
        successes = []

        if result.get("status") == "success":
            successes.append("Задача выполнена успешно")

        if "execution_log" in result:
            successes.append("Все шаги выполнены")

        return successes

    def _identify_improvements(self, result: dict[str, Any]) -> list[str]:
        """Идентификация улучшений"""
        improvements = []

        if "execution_time" in result:
            if result["execution_time"] > 10:
                improvements.append("Сократить время выполнения")

        if "errors" in result:
            improvements.append("Уменьшить количество ошибок")

        return improvements

    def _extract_lessons(self, result: dict[str, Any]) -> list[str]:
        """Извлечение уроков"""
        lessons = []

        if "meta_insight" in result:
            lessons.append(f"Мета-инсайт: {result['meta_insight']}")

        if "reasoning_analytics" in result:
            lessons.append("Использовать эффективные алгоритмы рассуждений")

        return lessons


class MindMapGenerator:
    """Генератор интеллект-карт"""

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Создание интеллект-карты из данных.

        Args:
            data: Данные для визуализации

        Returns:
            Структура интеллект-карты
        """
        mind_map = {"center": data.get("center", "Main Topic"), "branches": {}}

        # Создаем ветви из данных
        for key, value in data.items():
            if key != "center":
                mind_map["branches"][key] = self._process_branch(value)

        return mind_map

    def _process_branch(self, value: Any) -> Any:
        """Обработка ветви"""
        if isinstance(value, dict):
            return {k: self._process_branch(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._process_branch(item) for item in value]
        else:
            return value

    def visualize(self, mind_map: dict[str, Any]) -> str:
        """
        Визуализация интеллект-карты в текстовом формате.

        Args:
            mind_map: Структура интеллект-карты

        Returns:
            Текстовое представление
        """
        lines = [f"📊 Mind Map: {mind_map['center']}", ""]

        for branch, content in mind_map["branches"].items():
            lines.append(f"  ├─ {branch}")
            if isinstance(content, dict):
                for sub_branch, sub_content in content.items():
                    lines.append(f"  │  ├─ {sub_branch}: {sub_content}")
            elif isinstance(content, list):
                for item in content:
                    lines.append(f"  │  ├─ {item}")
            else:
                lines.append(f"  │  └─ {content}")

        return "\n".join(lines)


class SelfReflection:
    """Реализация саморефлексии"""

    def reflect(self, plan: dict[str, Any]) -> dict[str, Any]:
        """
        Саморефлексия перед выполнением.

        Args:
            plan: План для выполнения

        Returns:
            Результат саморефлексии
        """
        reflection = {
            "assumptions": self._identify_assumptions(plan),
            "biases": self._identify_biases(plan),
            "confidence": self._assess_confidence(plan),
            "alternatives": self._consider_alternatives(plan),
        }

        return reflection

    def _identify_assumptions(self, plan: dict[str, Any]) -> list[str]:
        """Идентификация предположений"""
        assumptions = []

        if "steps" in plan:
            assumptions.append("Предположение: все шаги выполнимы")

        if "timeout" in plan:
            assumptions.append(f"Предположение: выполнение займет < {plan['timeout']}s")

        return assumptions

    def _identify_biases(self, plan: dict[str, Any]) -> list[str]:
        """Идентификация предубеждений"""
        return ["Потенциальное предубеждение: оптимизм в оценке времени"]

    def _assess_confidence(self, plan: dict[str, Any]) -> float:
        """Оценка уверенности"""
        # Упрощенная оценка
        return 0.85

    def _consider_alternatives(self, plan: dict[str, Any]) -> list[str]:
        """Рассмотрение альтернатив"""
        return ["Альтернативный план 1", "Альтернативный план 2"]
