import random

from src.core.agent_thinking import AgentThinkingCoach


class MarketingAgent:
    """
    Agent for generating marketing copy for x0tta6bl4.
    """

    POST_TEMPLATES = [
        "🚀 *x0tta6bl4*: VPN, который не падает. Self-healing mesh архитектура из Крыма. Попробуй 7 дней бесплатно: {bot_link}",
        "🔥 Проблемы с YouTube? С x0tta6bl4 1080p летает без задержек. Работаем через PQC и eBPF. Старт: {bot_link}",
        "🔒 Твои данные — только твои. Локальное шифрование и Zero-Trust. x0tta6bl4 — это свобода. {bot_link}",
        "⚙️ Устал от того, что VPN тормозит? Наша сеть сама переключает узлы при сбоях. Будущее уже здесь: {bot_link}",
    ]

    def __init__(self, bot_username: str = "x0tta6bl4_bot"):
        self.bot_link = f"https://t.me/{bot_username}?start=gtm"
        self.thinking_coach = AgentThinkingCoach(
            agent_id="marketing",
            role="marketing",
            capabilities=("copywriting", "brainstorming", "framing"),
        )
        self.last_thinking_context = {}

    def generate_random_post(self) -> str:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "type": "marketing_copy",
                "goal": "generate a concise conversion-oriented post",
                "constraints": {"cta": self.bot_link},
            }
        )
        template = random.choice(self.POST_TEMPLATES)
        return template.format(bot_link=self.bot_link)


if __name__ == "__main__":
    agent = MarketingAgent()
    print("--- Сгенерированный пост ---")
    print(agent.generate_random_post())
