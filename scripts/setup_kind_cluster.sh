#!/bin/sh
set -o errexit

# 1. Определяем имя и порт реестра
reg_name='kind-registry'
reg_port='5001' # Порт на хост-машине, который будет проксировать к порту 5000 контейнера реестра

# 2. Создаем контейнер реестра, если он еще не существует
if [ "$(docker inspect -f '{{.State.Running}}' "${reg_name}" 2>/dev/null || true)" != 'true' ]; then
  echo "Создание локального реестра Docker..."
  docker run \
    -d --restart=always -p "127.0.0.1:${reg_port}:5000" --name "${reg_name}" \
    registry:2
fi

# 3. Создаем файл конфигурации кластера kind
echo "Создание файла конфигурации kind-config.yaml..."
cat <<EOF > kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: x0tta6bl4-staging
containerdConfigPatches:
- |-
  [plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:${reg_port}"]
    endpoint = ["http://${reg_name}:5000"]
  [plugins."io.containerd.grpc.v1.cri".proxy_plugins]
    [plugins."io.containerd.grpc.v1.cri".proxy_plugins.http_proxy]
      http_proxy = "http://127.0.0.1:10808"
      https_proxy = "http://127.0.0.1:10808"
      no_proxy = "localhost,127.0.0.1,0.0.0.0,10.96.0.0/12,192.168.0.0/16,172.16.0.0/12,kind-registry,.svc,.svc.cluster.local"
EOF

# 4. Создаем кластер kind с использованием конфигурации
echo "Создание кластера kind..."
kind create cluster --config=kind-config.yaml

# 5. Добавляем конфигурацию реестра на узлы кластера
# Это необходимо, потому что localhost внутри контейнера не является localhost на хосте.
# Мы хотим, чтобы containerd перенаправлял localhost:${reg_port} на контейнер реестра.
echo "Настройка узлов кластера для использования локального реестра..."
REGISTRY_DIR="/etc/containerd/certs.d/localhost:${reg_port}"
for node in $(kind get nodes --name x0tta6bl4-staging); do
  docker exec "${node}" mkdir -p "${REGISTRY_DIR}"
  cat <<EOF | docker exec -i "${node}" cp /dev/stdin "${REGISTRY_DIR}/hosts.toml"
[host."http://${reg_name}:5000"]
EOF
done

# 6. Подключаем реестр к сети кластера kind, если он еще не подключен
echo "Подключение реестра к сети кластера kind..."
if [ "$(docker inspect -f='{{json .NetworkSettings.Networks.kind}}' "${reg_name}")" = 'null' ]; then
  docker network connect "kind" "${reg_name}"
fi

# 7. Документируем локальный реестр в кластере
echo "Документирование локального реестра в кластере..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${reg_port}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF

echo "Кластер kind настроен для использования локального реестра на localhost:${reg_port}."
echo "Теперь вы можете собирать образы с тегом localhost:${reg_port}/your-image:tag и отправлять их в реестр."
echo "Например: docker build -t localhost:${reg_port}/my-app:latest . && docker push localhost:${reg_port}/my-app:latest"
echo "Затем используйте этот образ в ваших манифестах Kubernetes."
