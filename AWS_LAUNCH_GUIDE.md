# 🚀 AWS STAGING LAUNCH - ПОШАГОВЫЙ ГАЙД

**Вариант:** B - AWS Staging Launch  
**Время:** 4-6 часов  
**Дата:** 27 декабря 2025

---

## 📋 ПРЕДВАРИТЕЛЬНЫЕ ТРЕБОВАНИЯ

### AWS Account Setup
- [ ] AWS account создан
- [ ] AWS CLI установлен и настроен (`aws configure`)
- [ ] IAM user с правами: ECR, ECS, EC2, VPC, CloudWatch
- [ ] Docker установлен локально

### Проверка
```bash
# Проверить AWS CLI
aws sts get-caller-identity

# Проверить Docker
docker --version

# Проверить образ
docker images | grep x0tta6bl4
```

---

## 🚀 ШАГ 1: ECR SETUP (15 минут)

### 1.1 Создать ECR Repository

```bash
# Настроить переменные
export AWS_REGION="us-east-1"
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR_REPO="x0tta6bl4-app"

# Создать ECR repository
aws ecr create-repository \
    --repository-name $ECR_REPO \
    --region $AWS_REGION \
    --image-scanning-configuration scanOnPush=true

# Получить login token
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
```

### 1.2 Build и Push Image

```bash
cd /mnt/AC74CC2974CBF3DC

# Build image
docker build -t x0tta6bl4-app:staging -f Dockerfile.app .

# Tag для ECR
docker tag x0tta6bl4-app:staging \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:staging

# Push в ECR
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:staging
```

**Ожидаемое время:** 10-15 минут

---

## 🚀 ШАГ 2: ECS CLUSTER & SERVICE (15 минут)

### 2.1 Создать ECS Cluster

```bash
# Создать cluster
aws ecs create-cluster \
    --cluster-name x0tta6bl4-staging \
    --region $AWS_REGION

# Создать task definition
cat > task-definition.json <<EOF
{
  "family": "x0tta6bl4-staging",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "x0tta6bl4-app",
      "image": "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:staging",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "NODE_ID", "value": "staging-control-plane"},
        {"name": "ENVIRONMENT", "value": "staging"},
        {"name": "LOG_LEVEL", "value": "INFO"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/x0tta6bl4-staging",
          "awslogs-region": "$AWS_REGION",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
EOF

# Создать CloudWatch log group
aws logs create-log-group \
    --log-group-name /ecs/x0tta6bl4-staging \
    --region $AWS_REGION || true

# Зарегистрировать task definition
aws ecs register-task-definition \
    --cli-input-json file://task-definition.json \
    --region $AWS_REGION
```

### 2.2 Создать VPC и Security Group

```bash
# Создать VPC (или использовать default)
export VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text --region $AWS_REGION)

# Создать Security Group
export SG_ID=$(aws ec2 create-security-group \
    --group-name x0tta6bl4-staging-sg \
    --description "x0tta6bl4 staging security group" \
    --vpc-id $VPC_ID \
    --region $AWS_REGION \
    --query 'GroupId' --output text)

# Разрешить HTTP/HTTPS
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 8080 \
    --cidr 0.0.0.0/0 \
    --region $AWS_REGION

# Получить subnets
export SUBNET_IDS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query "Subnets[0:2].SubnetId" \
    --output text \
    --region $AWS_REGION | tr '\t' ',')
```

### 2.3 Создать ECS Service

```bash
# Создать service
aws ecs create-service \
    --cluster x0tta6bl4-staging \
    --service-name x0tta6bl4-staging-service \
    --task-definition x0tta6bl4-staging \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
    --region $AWS_REGION
```

**Ожидаемое время:** 10-15 минут

---

## 🚀 ШАГ 3: LOAD BALANCER + DNS (15 минут)

### 3.1 Создать Application Load Balancer

```bash
# Создать ALB
export ALB_ARN=$(aws elbv2 create-load-balancer \
    --name x0tta6bl4-staging-alb \
    --subnets $SUBNET_IDS \
    --security-groups $SG_ID \
    --region $AWS_REGION \
    --query 'LoadBalancers[0].LoadBalancerArn' --output text)

# Получить ALB DNS name
export ALB_DNS=$(aws elbv2 describe-load-balancers \
    --load-balancer-arns $ALB_ARN \
    --region $AWS_REGION \
    --query 'LoadBalancers[0].DNSName' --output text)

echo "ALB DNS: $ALB_DNS"
```

### 3.2 Создать Target Group

```bash
# Создать target group
export TG_ARN=$(aws elbv2 create-target-group \
    --name x0tta6bl4-staging-tg \
    --protocol HTTP \
    --port 8080 \
    --vpc-id $VPC_ID \
    --health-check-path /health \
    --health-check-interval-seconds 30 \
    --health-check-timeout-seconds 5 \
    --healthy-threshold-count 2 \
    --unhealthy-threshold-count 3 \
    --region $AWS_REGION \
    --query 'TargetGroups[0].TargetGroupArn' --output text)

# Создать listener
aws elbv2 create-listener \
    --load-balancer-arn $ALB_ARN \
    --protocol HTTP \
    --port 80 \
    --default-actions Type=forward,TargetGroupArn=$TG_ARN \
    --region $AWS_REGION
```

### 3.3 Обновить ECS Service для ALB

```bash
# Получить task ARN
export TASK_ARN=$(aws ecs list-tasks \
    --cluster x0tta6bl4-staging \
    --service-name x0tta6bl4-staging-service \
    --region $AWS_REGION \
    --query 'taskArns[0]' --output text)

# Получить ENI ID
export ENI_ID=$(aws ecs describe-tasks \
    --cluster x0tta6bl4-staging \
    --tasks $TASK_ARN \
    --region $AWS_REGION \
    --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text)

# Получить private IP
export PRIVATE_IP=$(aws ec2 describe-network-interfaces \
    --network-interface-ids $ENI_ID \
    --region $AWS_REGION \
    --query 'NetworkInterfaces[0].PrivateIpAddress' --output text)

# Зарегистрировать target
aws elbv2 register-targets \
    --target-group-arn $TG_ARN \
    --targets Id=$PRIVATE_IP,Port=8080 \
    --region $AWS_REGION
```

**Ожидаемое время:** 10-15 минут

---

## 🚀 ШАГ 4: MONITORING SETUP (30 минут)

### 4.1 CloudWatch Dashboard

```bash
# Создать dashboard
aws cloudwatch put-dashboard \
    --dashboard-name x0tta6bl4-staging \
    --dashboard-body file://dashboard.json \
    --region $AWS_REGION
```

### 4.2 Prometheus (опционально)

Если нужен Prometheus, можно использовать AWS Managed Prometheus или запустить на EC2.

---

## 🚀 ШАГ 5: SMOKE TESTS + LOAD TEST (30 минут)

### 5.1 Smoke Tests

```bash
# Дождаться пока ALB станет доступен (2-3 минуты)
sleep 180

# Health check
curl http://$ALB_DNS/health

# Metrics
curl http://$ALB_DNS/metrics

# Mesh peers
curl http://$ALB_DNS/mesh/peers
```

### 5.2 Load Test

```bash
# Запустить load test
python3 scripts/run_load_test.py --url http://$ALB_DNS
```

---

## ✅ ПРОВЕРКА

### Health Check
```bash
curl http://$ALB_DNS/health
# Ожидается: {"status":"ok","version":"3.0.0"}
```

### Metrics
```bash
curl http://$ALB_DNS/metrics
# Ожидается: Prometheus metrics
```

### ECS Service Status
```bash
aws ecs describe-services \
    --cluster x0tta6bl4-staging \
    --services x0tta6bl4-staging-service \
    --region $AWS_REGION \
    --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'
```

---

## 📊 МОНИТОРИНГ

### CloudWatch Metrics
- CPU Utilization
- Memory Utilization
- Request Count
- Error Rate
- Latency

### ECS Logs
```bash
aws logs tail /ecs/x0tta6bl4-staging --follow --region $AWS_REGION
```

---

## 🚨 TROUBLESHOOTING

### Service не запускается
```bash
# Проверить task status
aws ecs describe-tasks \
    --cluster x0tta6bl4-staging \
    --tasks $TASK_ARN \
    --region $AWS_REGION

# Проверить logs
aws logs tail /ecs/x0tta6bl4-staging --follow
```

### Health check fails
```bash
# Проверить security group
aws ec2 describe-security-groups --group-ids $SG_ID

# Проверить target group health
aws elbv2 describe-target-health --target-group-arn $TG_ARN
```

---

## 💰 СТОИМОСТЬ

```
ECR:          ~$1/month (storage)
ECS Fargate:  ~$30/month (1 task, 0.5 vCPU, 1GB RAM)
ALB:          ~$20/month
CloudWatch:   ~$10/month
Data Transfer: ~$10/month

TOTAL:        ~$70-100/month
```

---

## 🎯 СЛЕДУЮЩИЕ ШАГИ

После успешного запуска:
1. Monitor metrics 24/7 (first week)
2. Gather user feedback
3. Fix any issues
4. Scale if needed
5. Prepare for Jan 13 full production

---

**Дата:** 27 декабря 2025  
**Статус:** ✅ **READY TO EXECUTE**

