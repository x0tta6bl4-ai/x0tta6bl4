#!/bin/bash
# КРИТИЧЕСКИЙ СКРИПТ: Настройка авто-разблокировки LUKS
set -e

KEYFILE="/crypto_keyfile.bin"
DEVICE="/dev/sda3"

echo "=== Шаг 1: Создание файла-ключа ==="
if [ ! -f "$KEYFILE" ]; then
    dd if=/dev/urandom of="$KEYFILE" bs=512 count=4
    chmod 600 "$KEYFILE"
    echo "Файл-ключ создан: $KEYFILE"
else
    echo "Файл-ключ уже существует."
fi

echo ""
echo "=== Шаг 2: Регистрация ключа в LUKS ==="
echo "СЕЙЧАС ВАС ПОПРОСЯТ ВВЕСТИ ПАРОЛЬ ОТ ШИФРОВАНИЯ ДИСКА (тот, что при загрузке)."
cryptsetup luksAddKey "$DEVICE" "$KEYFILE"

echo ""
echo "=== Шаг 3: Обновление /etc/crypttab ==="
cp /etc/crypttab /etc/crypttab.bak
UUID=$(blkid -s UUID -o value "$DEVICE")
# Важно: для Ubuntu/Debian указываем путь к ключу и опции для initramfs
echo "dm_crypt-0 UUID=$UUID $KEYFILE luks,discard" > /etc/crypttab
echo "Обновлен /etc/crypttab (бэкап в /etc/crypttab.bak)"

echo ""
echo "=== Шаг 4: Настройка включения ключа в Initramfs ==="
# Устанавливаем маску для безопасности (только root может читать образ)
if grep -q "^UMASK=" /etc/initramfs-tools/initramfs.conf; then
    sed -i 's/^UMASK=.*/UMASK=0077/' /etc/initramfs-tools/initramfs.conf
else
    echo "UMASK=0077" >> /etc/initramfs-tools/initramfs.conf
fi

# Говорим cryptsetup-initramfs включать все ключи из /
if grep -q "^KEYFILE_PATTERN=" /etc/cryptsetup-initramfs/conf-hook; then
    sed -i 's|^#\?KEYFILE_PATTERN=.*|KEYFILE_PATTERN="/crypto_keyfile.bin"|' /etc/cryptsetup-initramfs/conf-hook
else
    echo 'KEYFILE_PATTERN="/crypto_keyfile.bin"' >> /etc/cryptsetup-initramfs/conf-hook
fi
echo "Настроено включение ключа в загрузочный образ."

echo ""
echo "=== Шаг 5: Обновление initramfs ==="
echo "Это включит ключ в загрузочный образ..."
update-initramfs -u

echo ""
echo "=== ГОТОВО! ==="
echo "Теперь диск должен расшифровываться автоматически при следующей загрузке."
echo "Вам больше не потребуется клавиатура для ввода пароля LUKS."
