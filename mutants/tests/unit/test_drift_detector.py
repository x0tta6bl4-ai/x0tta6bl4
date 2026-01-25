# tests/unit/test_drift_detector.py
import pytest
from x0tta6bl4_paradox_zone.src.drift_detector import DriftDetector, DriftReport

def test_initialization():
    """Тест базовой инициализации детектора."""
    baseline = {"latency_p95": 100.0, "error_rate": 0.05}
    detector = DriftDetector(baseline)
    assert detector.baseline == baseline
    assert detector.enable_advanced is True

# ----------------------------------------
# 5 Эдж-кейс тестов
# ----------------------------------------

def test_edge_case_1_baseline_with_zero_value():
    """
    Эдж-кейс 1: Проверяет, как детектор обрабатывает метрику, 
    где базовое значение равно 0. В этом случае должен использоваться
    абсолютный порог, а не процентное отклонение.
    """
    baseline = {"latency_p95": 100.0, "new_errors": 0.0}
    detector = DriftDetector(baseline, absolute_threshold=5.0)

    # Случай 1: Превышение абсолютного порога
    current = {"latency_p95": 110.0, "new_errors": 10.0}
    report = detector.update(current)
    
    assert "new_errors" in report.exceeded
    assert report.percent_diffs["new_errors"] == 1.0  # 1.0, так как превышен абсолютный порог

    # Случай 2: Непревышение абсолютного порога
    current_no_exceed = {"latency_p95": 110.0, "new_errors": 4.0}
    report_no_exceed = detector.update(current_no_exceed)
    assert "new_errors" not in report_no_exceed.exceeded
    assert report_no_exceed.percent_diffs["new_errors"] == 0.0

def test_edge_case_2_update_with_empty_current_dict():
    """
    Эдж-кейс 2: Проверяет поведение при вызове update с пустым словарем.
    Ожидается, что значения из baseline будут использованы как текущие, 
    и дрейф будет равен 0.
    """
    baseline = {"latency_p95": 100.0, "error_rate": 0.05}
    detector = DriftDetector(baseline)
    
    current = {}
    report = detector.update(current)
    
    assert report.drift_score == 0.0
    assert not report.exceeded
    assert report.percent_diffs["latency_p95"] == 0.0
    assert report.percent_diffs["error_rate"] == 0.0

def test_edge_case_3_update_with_missing_keys():
    """
    Эдж-кейс 3: Проверяет поведение, когда в current отсутствуют некоторые
    ключи, которые есть в baseline. Ожидается, что для отсутствующих
    ключей будут использованы значения из baseline.
    """
    baseline = {"latency_p95": 100.0, "error_rate": 0.05, "cpu_usage": 0.5}
    detector = DriftDetector(baseline)
    
    current = {"latency_p95": 130.0} # error_rate и cpu_usage отсутствуют
    report = detector.update(current)
    
    assert report.drift_score > 0.0
    assert "latency_p95" in report.exceeded # 30% > 25%
    assert "error_rate" not in report.exceeded
    assert "cpu_usage" not in report.exceeded
    assert report.percent_diffs["latency_p95"] == pytest.approx(0.3)
    assert report.percent_diffs["error_rate"] == 0.0
    assert report.percent_diffs["cpu_usage"] == 0.0

def test_edge_case_4_advanced_mode_with_insufficient_history():
    """
    Эдж-кейс 4: Проверяет, что продвинутый режим не вызывает ошибок, 
    когда в истории недостаточно данных для вычисления z-score или сезонности.
    Классификация должна оставаться 'none'.
    """
    baseline = {"metric": 100}
    detector = DriftDetector(baseline, enable_advanced=True, seasonal_window=10)
    
    # Делаем 3 обновления (меньше, чем 5, необходимых для z-score, и меньше seasonal_window)
    detector.update({"metric": 105})
    detector.update({"metric": 98})
    report = detector.update({"metric": 150}) # Большой скачок
    
    # Классификация должна быть 'spike' из-за большого относительного отклонения, даже без z-score.
    assert report.classification == "spike"
    assert "|diff|>=0.5" in report.reasons[0]
    assert "|diff|>=0.5" in report.reasons[0]
    assert not report.z_scores
    assert "metric" in report.exceeded

def test_edge_case_5_spike_detection_in_basic_mode():
    """
    Эдж-кейс 5: Проверяет, что несмотря на то, что классификация "spike"
    доступна только в продвинутом режиме, отчет все равно корректно
    фиксирует превышение порога в базовом режиме.
    """
    baseline = {"metric": 100}
    detector = DriftDetector(baseline, enable_advanced=False, thresholds={"metric": 0.2})
    
    current = {"metric": 150} # 50% дрейф
    report = detector.update(current)
    
    assert report.classification == "none" # Классификация отключена
    assert "metric" in report.exceeded
    assert report.drift_score == pytest.approx(0.5)
