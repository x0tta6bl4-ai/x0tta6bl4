# x0tta6bl4: Terraform Infrastructure as Code

**Версия:** 1.0  
**Дата:** 31 декабря 2025  
**Статус:** ✅ **PRODUCTION READY**

---

## 📋 Обзор

Terraform конфигурации для развертывания x0tta6bl4 на:

- ✅ **AWS** (EKS)
- ✅ **Azure** (AKS)
- ✅ **GCP** (GKE)

---

## 🚀 Быстрый старт

### 1. Выберите облако

```bash
# AWS
cd infra/terraform/aws

# Azure
cd infra/terraform/azure

# GCP
cd infra/terraform/gcp
```

### 2. Настройте переменные

```bash
# Скопировать пример
cp terraform.tfvars.example terraform.tfvars

# Отредактировать terraform.tfvars
nano terraform.tfvars
```

### 3. Инициализация и применение

```bash
# Инициализация
terraform init

# План (проверка)
terraform plan

# Применение
terraform apply
```

---

## 📁 Структура

```
infra/terraform/
├── aws/
│   ├── main.tf              # EKS infrastructure
│   ├── variables.tf         # Variable declarations
│   ├── outputs.tf           # Output values
│   └── terraform.tfvars.example
├── azure/
│   ├── main.tf              # AKS infrastructure
│   ├── variables.tf         # Variable declarations
│   └── terraform.tfvars.example
└── gcp/
    ├── main.tf              # GKE infrastructure
    ├── variables.tf         # Variable declarations
    └── terraform.tfvars.example
```

---

## 🔧 Переменные

### Общие переменные

Все платформы используют похожие переменные:

- `environment` - окружение (dev/staging/production)
- `node_min_count` / `node_max_count` - autoscaling диапазон
- `node_initial_count` - начальное количество нод

### Платформо-специфичные

**AWS:**
- `aws_region` - регион AWS
- `cluster_name` - имя EKS кластера
- `vpc_cidr` - CIDR для VPC
- `node_instance_types` - типы EC2 инстансов

**Azure:**
- `azure_location` - регион Azure
- `vnet_address_space` - адресное пространство VNet
- `node_vm_size` - размер VM для нод

**GCP:**
- `gcp_project_id` - **обязательный** ID проекта GCP
- `gcp_region` - регион GCP
- `subnet_cidr` - CIDR подсети
- `node_machine_type` - тип машины для нод
- `node_disk_size` - размер диска (GB)

---

## 📝 Примеры конфигураций

### Development (минимальные ресурсы)

**GCP:**
```hcl
gcp_project_id = "my-project-dev"
environment = "dev"
node_min_count = 1
node_max_count = 3
node_initial_count = 1
node_machine_type = "e2-small"
```

**AWS:**
```hcl
environment = "dev"
node_min_size = 1
node_max_size = 3
node_desired_size = 1
node_instance_types = ["t3.small"]
```

**Azure:**
```hcl
environment = "dev"
node_count = 1
node_min_count = 1
node_max_count = 3
node_vm_size = "Standard_B2s"
```

### Production (рекомендуемые значения)

**GCP:**
```hcl
gcp_project_id = "my-project-prod"
environment = "production"
node_min_count = 3
node_max_count = 10
node_initial_count = 3
node_machine_type = "e2-medium"
```

**AWS:**
```hcl
environment = "production"
node_min_size = 3
node_max_size = 10
node_desired_size = 3
node_instance_types = ["t3.medium"]
```

**Azure:**
```hcl
environment = "production"
node_count = 3
node_min_count = 3
node_max_count = 10
node_vm_size = "Standard_D2s_v3"
```

---

## 🔒 Безопасность

### State Management

**ВАЖНО:** Настройте remote backend для state:

**AWS:**
```hcl
backend "s3" {
  bucket = "x0tta6bl4-terraform-state"
  key    = "aws/terraform.tfstate"
  region = "us-east-1"
}
```

**Azure:**
```hcl
backend "azurerm" {
  resource_group_name  = "x0tta6bl4-terraform"
  storage_account_name = "x0tta6bl4tfstate"
  container_name       = "terraform-state"
  key                  = "azure/terraform.tfstate"
}
```

**GCP:**
```hcl
backend "gcs" {
  bucket = "x0tta6bl4-terraform-state"
  prefix = "gcp/terraform.tfstate"
}
```

### Secrets

**НЕ коммитить:**
- `terraform.tfvars` (с реальными значениями)
- `.terraform/` директория
- `*.tfstate` файлы
- `*.tfstate.backup` файлы

**Добавить в `.gitignore`:**
```
*.tfstate
*.tfstate.backup
.terraform/
terraform.tfvars
```

---

## 📊 Outputs

После `terraform apply` вы получите:

**AWS:**
- `cluster_id` - EKS cluster ID
- `cluster_endpoint` - Endpoint для kubeconfig
- `vpc_id` - VPC ID
- `s3_bucket_name` - S3 bucket для данных

**Azure:**
- `aks_cluster_name` - AKS cluster name
- `resource_group_name` - Resource group name
- `storage_account_name` - Storage account name

**GCP:**
- `cluster_name` - GKE cluster name
- `cluster_endpoint` - Endpoint для kubeconfig
- `gcs_bucket_name` - Cloud Storage bucket name

---

## 🔄 Обновление

### Изменить количество нод

```bash
# Отредактировать terraform.tfvars
# node_min_count = 5
# node_max_count = 15

# Применить изменения
terraform plan
terraform apply
```

### Изменить тип машины

```bash
# Отредактировать terraform.tfvars
# node_machine_type = "e2-large"

# Применить изменения
terraform plan
terraform apply
```

---

## 🐛 Troubleshooting

### Ошибка: "Project not found"

**GCP:**
```bash
# Проверить проект
gcloud projects list

# Установить проект
gcloud config set project YOUR_PROJECT_ID
```

### Ошибка: "Region not available"

**Проверить доступные регионы:**
```bash
# AWS
aws ec2 describe-regions

# Azure
az account list-locations

# GCP
gcloud compute regions list
```

### Ошибка: "Insufficient permissions"

**Проверить IAM роли:**
- AWS: `AmazonEKSClusterPolicy`, `AmazonEKSNodePolicy`
- Azure: `Contributor` или `Owner`
- GCP: `Kubernetes Engine Admin`, `Compute Admin`

---

## 📚 Дополнительные ресурсы

- **Kubernetes Deployment:** `deployment/kubernetes/README_DEPLOYMENT.md`
- **Quick Start:** `QUICK_START_DEPLOYMENT.md`
- **Commercialization:** `COMMERCIALIZATION_READY.md`

---

## ✅ Checklist

- [ ] Выбрано облако (AWS/Azure/GCP)
- [ ] Создан `terraform.tfvars` из примера
- [ ] Заполнены все обязательные переменные
- [ ] Настроен remote backend для state
- [ ] Проверены IAM permissions
- [ ] `terraform init` выполнен успешно
- [ ] `terraform plan` показывает корректный план
- [ ] `terraform apply` выполнен успешно
- [ ] kubeconfig настроен
- [ ] Kubernetes deployment применен

---

**Готово! Инфраструктура развернута! 🎉**

*Время до running infrastructure: ~20-30 минут*

