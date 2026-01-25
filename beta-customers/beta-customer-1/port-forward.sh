#!/bin/bash
# Port-forward для доступа к x0tta6bl4-staging
# Запусти этот скрипт для доступа к сервису

kubectl port-forward -n x0tta6bl4-staging svc/x0tta6bl4-staging 8080:8080 &
echo "Port-forward запущен. Доступ: http://localhost:8080"
echo "Нажми Ctrl+C для остановки"
wait
