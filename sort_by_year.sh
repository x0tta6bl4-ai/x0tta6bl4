#!/bin/bash
while true; do
    exiftool -d "/mnt/projects/СЕМЕЙНЫЙ_АРХИВ_ИТОГ/%Y" "-directory<CreateDate" "-directory<DateTimeOriginal" /mnt/projects/СЕМЕЙНЫЙ_АРХИВ_ИТОГ/*.jpg 2>/dev/null
    sleep 30
done
