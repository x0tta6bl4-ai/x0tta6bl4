from xray_client_naming import build_human_xray_email


def test_build_human_xray_email_uses_transliterated_username_and_known_device():
    assert (
        build_human_xray_email(
            user_id=123,
            username="Имя Тест",
            device_name="мой телефон",
            user_uuid="unused",
        )
        == "imya_test__123__my_phone"
    )


def test_build_human_xray_email_keeps_numbered_device_patterns():
    assert (
        build_human_xray_email(
            user_id=77,
            username="@TestUser",
            device_name="рабочий ноутбук 2",
            user_uuid="unused",
        )
        == "testuser__77__work_laptop_2"
    )


def test_build_human_xray_email_falls_back_for_empty_values():
    assert (
        build_human_xray_email(
            user_id=5,
            username=None,
            device_name=None,
            user_uuid="unused",
        )
        == "user5__5__device"
    )
