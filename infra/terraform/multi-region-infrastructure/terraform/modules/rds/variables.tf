# Переменные для модуля RDS

variable "identifier" {
  description = "Идентификатор кластера базы данных"
  type        = string
}

variable "environment" {
  description = "Среда развертывания"
  type        = string
  default     = "production"
}

variable "engine" {
  description = "Движок базы данных"
  type        = string
  default     = "aurora-mysql"
}

variable "engine_version" {
  description = "Версия движка базы данных"
  type        = string
  default     = "8.0.mysql_aurora.3.04.0"
}

variable "instance_class" {
  description = "Класс инстанса базы данных"
  type        = string
  default     = "db.t3.medium"
}

variable "allocated_storage" {
  description = "Выделенное хранилище в GB"
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "Максимальное выделенное хранилище в GB"
  type        = number
  default     = 1000
}

variable "database_name" {
  description = "Имя базы данных"
  type        = string
  default     = "x0tta6bl4"
}

variable "master_username" {
  description = "Имя пользователя базы данных"
  type        = string
  default     = "admin"
}

variable "master_password" {
  description = "Пароль базы данных (если не используется manage_master_user_password)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "manage_master_user_password" {
  description = "Автоматически управлять паролем базы данных"
  type        = bool
  default     = true
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "db_subnet_group_name" {
  description = "Имя DB subnet group"
  type        = string
}

variable "security_group_id" {
  description = "Security Group ID для базы данных"
  type        = string
}

variable "global_cluster_identifier" {
  description = "Идентификатор глобального кластера (для реплик)"
  type        = string
  default     = ""
}

variable "create_global_cluster" {
  description = "Создать глобальный кластер"
  type        = bool
  default     = false
}

variable "backup_retention_period" {
  description = "Период хранения бэкапов в днях"
  type        = number
  default     = 30
}

variable "backup_window" {
  description = "Окно бэкапирования"
  type        = string
  default     = "03:00-04:00"
}

variable "maintenance_window" {
  description = "Окно обслуживания"
  type        = string
  default     = "sun:04:00-sun:05:00"
}

variable "deletion_protection" {
  description = "Защита от удаления"
  type        = bool
  default     = true
}

variable "skip_final_snapshot" {
  description = "Пропустить финальный снапшот при удалении"
  type        = bool
  default     = false
}

variable "storage_encrypted" {
  description = "Шифрование хранилища"
  type        = bool
  default     = true
}

variable "kms_key_id" {
  description = "KMS ключ для шифрования"
  type        = string
  default     = ""
}

variable "enabled_cloudwatch_logs_exports" {
  description = "Включить экспорт логов в CloudWatch"
  type        = list(string)
  default     = ["audit", "error", "general", "slowquery"]
}

variable "monitoring_interval" {
  description = "Интервал мониторинга в секундах"
  type        = number
  default     = 60
}

variable "monitoring_role_arn" {
  description = "ARN роли для мониторинга"
  type        = string
  default     = ""
}

variable "auto_minor_version_upgrade" {
  description = "Автоматическое обновление минорных версий"
  type        = bool
  default     = true
}

variable "apply_immediately" {
  description = "Применять изменения немедленно"
  type        = bool
  default     = false
}

variable "instance_count" {
  description = "Количество инстансов в кластере"
  type        = number
  default     = 2
}

variable "alarm_actions" {
  description = "Список ARN для действий алертов"
  type        = list(string)
  default     = []
}

variable "alert_emails" {
  description = "Email адреса для алертов"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Теги для ресурсов"
  type        = map(string)
  default     = {}
}