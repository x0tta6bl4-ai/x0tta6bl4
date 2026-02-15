"""
Тесты для Differential Privacy в Federated Learning.

Покрывает:
- Gradient clipping
- Gaussian noise generation
- Privacy budget tracking
- Secure Aggregation
- DP-SGD privacy guarantees
"""

import math
from typing import List

import pytest

from src.federated_learning.privacy import (DifferentialPrivacy, DPConfig,
                                            GaussianNoiseGenerator,
                                            GradientClipper, PrivacyBudget,
                                            SecureAggregation,
                                            compute_dp_sgd_privacy)


class TestGradientClipper:
    """Тесты для GradientClipper."""

    def test_no_clip_when_below_threshold(self, gradient_clipper):
        """Не обрезает если норма ниже порога."""
        gradients = [0.3, 0.4]  # Норма = 0.5 < 1.0
        clipped, norm = gradient_clipper.clip(gradients)

        assert clipped == gradients
        assert abs(norm - 0.5) < 1e-6

    def test_clips_when_above_threshold(self, gradient_clipper):
        """Обрезает если норма выше порога."""
        gradients = [3.0, 4.0]  # Норма = 5.0 > 1.0
        clipped, norm = gradient_clipper.clip(gradients)

        # Норма clipped должна быть 1.0
        clipped_norm = math.sqrt(sum(g * g for g in clipped))
        assert abs(clipped_norm - 1.0) < 1e-6
        assert norm == 5.0

    def test_clip_preserves_direction(self, gradient_clipper):
        """Clipping сохраняет направление."""
        gradients = [6.0, 8.0]  # Норма = 10.0
        clipped, _ = gradient_clipper.clip(gradients)

        # Направление (пропорции) должно сохраниться
        ratio_original = gradients[0] / gradients[1]
        ratio_clipped = clipped[0] / clipped[1]
        assert abs(ratio_original - ratio_clipped) < 1e-6

    def test_clip_rate_tracking(self, gradient_clipper):
        """Отслеживание процента обрезанных."""
        # Один ниже порога, один выше
        gradient_clipper.clip([0.3, 0.4])  # не обрежет
        gradient_clipper.clip([3.0, 4.0])  # обрежет

        assert gradient_clipper.clip_rate == 0.5

    def test_clip_batch(self, gradient_clipper):
        """Batch clipping."""
        batch = [
            [0.3, 0.4],  # не обрежет
            [3.0, 4.0],  # обрежет
            [0.6, 0.8],  # не обрежет
        ]

        clipped, norms = gradient_clipper.clip_batch(batch)

        assert len(clipped) == 3
        assert len(norms) == 3

    def test_reset_stats(self, gradient_clipper):
        """Сброс статистики."""
        gradient_clipper.clip([3.0, 4.0])
        gradient_clipper.reset_stats()

        assert gradient_clipper.clip_rate == 0.0


class TestGaussianNoiseGenerator:
    """Тесты для GaussianNoiseGenerator."""

    def test_generate_noise_size(self, noise_generator):
        """Генерация шума правильного размера."""
        noise = noise_generator.generate(size=100, scale=1.0)
        assert len(noise) == 100

    def test_generate_noise_scale(self, noise_generator):
        """Шум имеет правильный масштаб."""
        noise = noise_generator.generate(size=10000, scale=2.0)

        # Стандартное отклонение должно быть близко к scale
        mean = sum(noise) / len(noise)
        variance = sum((n - mean) ** 2 for n in noise) / len(noise)
        std = math.sqrt(variance)

        assert abs(std - 2.0) < 0.2  # С погрешностью

    def test_reproducible_with_seed(self):
        """Воспроизводимость с фиксированным seed."""
        gen1 = GaussianNoiseGenerator(seed=42)
        gen2 = GaussianNoiseGenerator(seed=42)

        noise1 = gen1.generate(10, 1.0)
        noise2 = gen2.generate(10, 1.0)

        assert noise1 == noise2

    def test_different_seeds_different_noise(self):
        """Разные seeds дают разный шум."""
        gen1 = GaussianNoiseGenerator(seed=42)
        gen2 = GaussianNoiseGenerator(seed=123)

        noise1 = gen1.generate(10, 1.0)
        noise2 = gen2.generate(10, 1.0)

        assert noise1 != noise2

    def test_calibrate_noise_positive_epsilon(self, noise_generator):
        """Калибровка шума требует положительный epsilon."""
        sigma = noise_generator.calibrate_noise(
            sensitivity=1.0, epsilon=1.0, delta=1e-5
        )

        assert sigma > 0

    def test_calibrate_noise_invalid_epsilon(self, noise_generator):
        """Калибровка с невалидным epsilon вызывает ошибку."""
        with pytest.raises(ValueError, match="Epsilon must be positive"):
            noise_generator.calibrate_noise(sensitivity=1.0, epsilon=0, delta=1e-5)

    def test_calibrate_noise_invalid_delta(self, noise_generator):
        """Калибровка с невалидным delta вызывает ошибку."""
        with pytest.raises(ValueError, match="Delta must be in"):
            noise_generator.calibrate_noise(sensitivity=1.0, epsilon=1.0, delta=1.5)

    def test_smaller_epsilon_larger_noise(self, noise_generator):
        """Меньший epsilon требует больше шума."""
        sigma_small_eps = noise_generator.calibrate_noise(
            sensitivity=1.0, epsilon=0.1, delta=1e-5
        )
        sigma_large_eps = noise_generator.calibrate_noise(
            sensitivity=1.0, epsilon=1.0, delta=1e-5
        )

        assert sigma_small_eps > sigma_large_eps


class TestPrivacyBudget:
    """Тесты для PrivacyBudget."""

    def test_initial_budget(self):
        """Начальный бюджет."""
        budget = PrivacyBudget()

        assert budget.epsilon == 0.0
        assert budget.rounds_participated == 0

    def test_add_round(self):
        """Добавление раунда."""
        budget = PrivacyBudget()
        budget.add_round(epsilon_spent=0.1, noise_scale=1.0)

        assert budget.epsilon == 0.1
        assert budget.rounds_participated == 1
        assert len(budget.noise_scales) == 1

    def test_cumulative_epsilon(self):
        """Накопление epsilon."""
        budget = PrivacyBudget()
        budget.add_round(0.1, 1.0)
        budget.add_round(0.1, 1.0)
        budget.add_round(0.1, 1.0)

        assert budget.epsilon == pytest.approx(0.3)

    def test_remaining_budget(self):
        """Оставшийся бюджет."""
        budget = PrivacyBudget()
        budget.add_round(0.3, 1.0)

        remaining = budget.remaining(max_epsilon=1.0)
        assert remaining == 0.7

    def test_is_exhausted(self):
        """Проверка исчерпания бюджета."""
        budget = PrivacyBudget()

        assert budget.is_exhausted(max_epsilon=1.0) is False

        budget.add_round(1.0, 1.0)
        assert budget.is_exhausted(max_epsilon=1.0) is True

    def test_to_dict(self):
        """Сериализация бюджета."""
        budget = PrivacyBudget()
        budget.add_round(0.5, 1.5)

        data = budget.to_dict()
        assert data["epsilon"] == 0.5
        assert data["rounds_participated"] == 1
        assert data["avg_noise_scale"] == 1.5


class TestDifferentialPrivacy:
    """Тесты для DifferentialPrivacy."""

    def test_dp_initialization(self, differential_privacy):
        """Инициализация DP."""
        assert differential_privacy.config is not None
        assert differential_privacy._noise_scale > 0

    def test_privatize_gradients(self, differential_privacy):
        """Приватизация градиентов."""
        gradients = [1.0, 2.0, 3.0]
        privatized, metadata = differential_privacy.privatize_gradients(gradients)

        # Размер сохраняется
        assert len(privatized) == len(gradients)

        # Должен быть добавлен шум
        assert privatized != gradients

        # Метаданные содержат информацию
        assert "noise_scale" in metadata
        assert "epsilon_spent" in metadata

    def test_gradient_clipping_applied(self, differential_privacy):
        """Clipping применяется."""
        # Большой градиент
        gradients = [100.0, 100.0]
        privatized, metadata = differential_privacy.privatize_gradients(gradients)

        assert metadata["clipped"] is True

    def test_privacy_budget_tracked(self, differential_privacy):
        """Privacy budget отслеживается."""
        initial_epsilon = differential_privacy.budget.epsilon

        differential_privacy.privatize_gradients([1.0, 2.0])

        assert differential_privacy.budget.epsilon > initial_epsilon

    def test_get_privacy_spent(self, differential_privacy):
        """Получение потраченного privacy."""
        differential_privacy.privatize_gradients([1.0])

        epsilon, delta = differential_privacy.get_privacy_spent()
        assert epsilon > 0
        assert delta == differential_privacy.config.target_delta

    def test_can_continue_training(self, differential_privacy):
        """Проверка возможности продолжения тренировки."""
        assert differential_privacy.can_continue_training() is True

        # Исчерпываем бюджет
        differential_privacy.budget.epsilon = (
            differential_privacy.config.target_epsilon + 1
        )

        assert differential_privacy.can_continue_training() is False

    def test_get_stats(self, differential_privacy):
        """Получение статистики DP."""
        stats = differential_privacy.get_stats()

        assert "config" in stats
        assert "budget" in stats
        assert "clip_rate" in stats
        assert "noise_scale" in stats
        assert "can_continue" in stats


class TestSecureAggregation:
    """Тесты для Secure Aggregation."""

    def test_initialization(self, secure_aggregation):
        """Инициализация Secure Aggregation."""
        assert secure_aggregation.num_parties == 5
        assert secure_aggregation.threshold == 3

    def test_generate_masks(self, secure_aggregation):
        """Генерация масок."""
        mask, seeds = secure_aggregation.generate_masks(party_id=0, vector_size=10)

        assert len(mask) == 10
        assert len(seeds) == 4  # Для остальных 4 участников

    def test_masks_cancel_out(self, secure_aggregation):
        """Маски взаимно уничтожаются."""
        vector_size = 10

        # Генерируем маски для всех участников
        masks = []
        for party_id in range(5):
            mask, _ = secure_aggregation.generate_masks(party_id, vector_size)
            masks.append(mask)

        # Сумма всех масок должна быть ~0
        total = [0.0] * vector_size
        for mask in masks:
            for i, v in enumerate(mask):
                total[i] += v

        # Допускаем небольшую погрешность из-за floating point
        for v in total:
            assert abs(v) < 1e-10

    def test_mask_update(self, secure_aggregation):
        """Маскирование обновления."""
        update = [1.0, 2.0, 3.0, 4.0, 5.0]
        masked = secure_aggregation.mask_update(update, party_id=0)

        # Маскированное обновление отличается
        assert masked != update
        assert len(masked) == len(update)

    def test_aggregate_masked_recovers_sum(self, secure_aggregation):
        """Агрегация восстанавливает сумму."""
        vector_size = 10

        # Создаём обновления
        updates = [[float(i) for _ in range(vector_size)] for i in range(5)]

        # Маскируем
        masked_updates = [
            secure_aggregation.mask_update(update, party_id=i)
            for i, update in enumerate(updates)
        ]

        # Агрегируем
        result = secure_aggregation.aggregate_masked(masked_updates)

        # Ожидаемая сумма: 0+1+2+3+4 = 10 для каждой координаты
        expected = [10.0] * vector_size

        for r, e in zip(result, expected):
            assert abs(r - e) < 1e-6

    def test_aggregate_empty_list(self, secure_aggregation):
        """Агрегация пустого списка."""
        result = secure_aggregation.aggregate_masked([])
        assert result == []


class TestDPSGDPrivacy:
    """Тесты для compute_dp_sgd_privacy."""

    def test_basic_computation(self):
        """Базовое вычисление privacy."""
        epsilon = compute_dp_sgd_privacy(
            sample_rate=0.01, noise_multiplier=1.0, epochs=10, delta=1e-5
        )

        assert epsilon > 0

    def test_more_epochs_more_privacy_loss(self):
        """Больше эпох - больше потеря privacy."""
        epsilon_few = compute_dp_sgd_privacy(
            sample_rate=0.01, noise_multiplier=1.0, epochs=10, delta=1e-5
        )
        epsilon_many = compute_dp_sgd_privacy(
            sample_rate=0.01, noise_multiplier=1.0, epochs=100, delta=1e-5
        )

        assert epsilon_many > epsilon_few

    def test_more_noise_less_privacy_loss(self):
        """Больше шума - меньше потеря privacy."""
        epsilon_low_noise = compute_dp_sgd_privacy(
            sample_rate=0.01, noise_multiplier=0.5, epochs=10, delta=1e-5
        )
        epsilon_high_noise = compute_dp_sgd_privacy(
            sample_rate=0.01, noise_multiplier=2.0, epochs=10, delta=1e-5
        )

        assert epsilon_high_noise < epsilon_low_noise


class TestDPIntegration:
    """Интеграционные тесты DP."""

    def test_full_dp_workflow(self, dp_config):
        """Полный workflow DP."""
        dp = DifferentialPrivacy(config=dp_config)

        # Несколько раундов приватизации
        for _ in range(5):
            gradients = [1.0, 2.0, 3.0, 4.0, 5.0]
            privatized, _ = dp.privatize_gradients(gradients, num_samples=100)

            # Проверяем что градиенты изменены
            assert privatized != gradients

        # Проверяем privacy budget
        epsilon, delta = dp.get_privacy_spent()
        assert epsilon > 0
        assert epsilon <= dp.config.target_epsilon * 2  # С запасом

    def test_dp_with_model_updates(self, differential_privacy, simple_weights):
        """DP с model weights."""
        flat_weights = simple_weights.to_flat_vector()

        privatized, metadata = differential_privacy.privatize_model_update(
            flat_weights, num_samples=1000
        )

        assert len(privatized) == len(flat_weights)
        assert metadata["total_epsilon"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
