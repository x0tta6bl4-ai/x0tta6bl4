# Расширенная конфигурация Cloudflare Global Load Balancer для x0tta6bl4

terraform {
  required_version = ">= 1.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Данные из региональных конфигураций
data "terraform_remote_state" "us_east_1" {
  backend = "s3"

  config = {
    bucket = "x0tta6bl4-terraform-state"
    key    = "us-east-1/terraform.tfstate"
    region = "us-east-1"
  }
}

data "terraform_remote_state" "eu_west_1" {
  backend = "s3"

  config = {
    bucket = "x0tta6bl4-terraform-state"
    key    = "eu-west-1/terraform.tfstate"
    region = "us-east-1"
  }
}

data "terraform_remote_state" "ap_southeast_1" {
  backend = "s3"

  config = {
    bucket = "x0tta6bl4-terraform-state"
    key    = "ap-southeast-1/terraform.tfstate"
    region = "us-east-1"
  }
}

# Глобальный мониторинг дашборд для Load Balancer
resource "aws_cloudwatch_dashboard" "global_lb_dashboard" {
  dashboard_name = "${var.project_name}-global-lb-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ApplicationELB", "ActiveConnectionCount", "LoadBalancer", data.terraform_remote_state.us_east_1.outputs.load_balancer_arn_suffix],
            [".", ".", ".", data.terraform_remote_state.eu_west_1.outputs.load_balancer_arn_suffix],
            [".", ".", ".", data.terraform_remote_state.ap_southeast_1.outputs.load_balancer_arn_suffix]
          ]
          view    = "timeSeries"
          stacked = false
          region  = "us-east-1"
          title   = "Global ALB Active Connections"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_Target_2XX_Count", "LoadBalancer", data.terraform_remote_state.us_east_1.outputs.load_balancer_arn_suffix],
            [".", "HTTPCode_Target_4XX_Count", ".", data.terraform_remote_state.us_east_1.outputs.load_balancer_arn_suffix],
            [".", "HTTPCode_Target_5XX_Count", ".", data.terraform_remote_state.us_east_1.outputs.load_balancer_arn_suffix]
          ]
          view    = "timeSeries"
          stacked = false
          region  = "us-east-1"
          title   = "US East 1 ALB HTTP Response Codes"
          period  = 300
        }
      }
    ]
  })
}

# Расширенный глобальный Load Balancer с географическим распределением
resource "cloudflare_load_balancer" "x0tta6bl4_global_lb" {
  zone_id          = var.cloudflare_zone_id
  name             = "x0tta6bl4-global-lb"
  fallback_pool_id = cloudflare_load_balancer_pool.x0tta6bl4_emea_pool.id
  default_pools    = [
    cloudflare_load_balancer_pool.x0tta6bl4_emea_pool.id,
    cloudflare_load_balancer_pool.x0tta6bl4_apac_pool.id,
    cloudflare_load_balancer_pool.x0tta6bl4_americas_pool.id
  ]

  # Географическое распределение трафика
  region_pools {
    region = "WNAM"  # Western North America
    pool_ids = [cloudflare_load_balancer_pool.x0tta6bl4_americas_pool.id]
  }

  region_pools {
    region = "ENAM"  # Eastern North America
    pool_ids = [cloudflare_load_balancer_pool.x0tta6bl4_americas_pool.id]
  }

  region_pools {
    region = "WEU"   # Western Europe
    pool_ids = [cloudflare_load_balancer_pool.x0tta6bl4_emea_pool.id]
  }

  region_pools {
    region = "EEU"   # Eastern Europe
    pool_ids = [cloudflare_load_balancer_pool.x0tta6bl4_emea_pool.id]
  }

  region_pools {
    region = "APAC"  # Asia Pacific
    pool_ids = [cloudflare_load_balancer_pool.x0tta6bl4_apac_pool.id]
  }

  region_pools {
    region = "OC"    # Oceania
    pool_ids = [cloudflare_load_balancer_pool.x0tta6bl4_apac_pool.id]
  }

  # Расширенный мониторинг состояния
  health_check {
    type                   = "HTTPS"
    method                 = "GET"
    path                   = "/health"
    port                   = 443
    timeout                = 5
    interval               = 60
    retries                = 3
    follow_redirects       = true
    allow_insecure         = false
  }

  # Настройки сессии для лучшего пользовательского опыта
  session_affinity       = "cookie"
  session_affinity_ttl   = 1800
  session_affinity_attributes = {
    samesite = "Auto"
    secure   = "Auto"
  }

  # Настройки производительности
  steering_policy        = "dynamic_latency"
  random_steering        = {
    default_weight = 50
    pool_weights = {
      cloudflare_load_balancer_pool.x0tta6bl4_americas_pool.id = 60
      cloudflare_load_balancer_pool.x0tta6bl4_emea_pool.id     = 70
      cloudflare_load_balancer_pool.x0tta6bl4_apac_pool.id     = 50
    }
  }

  # Адаптивное распределение нагрузки
  adaptive_routing {
    enabled = true
  }

  # Защита от DDoS на уровне load balancer
  rules {
    name      = "DDoS Protection"
    condition = "cf.threat_score gt 50"
    action    = "managed_challenge"
  }

  rules {
    name      = "Rate Limiting"
    condition = "http.request.rate gt 100"
    action    = "managed_challenge"
  }
}

# Пул серверов для Americas региона (us-east-1)
resource "cloudflare_load_balancer_pool" "x0tta6bl4_americas_pool" {
  name         = "x0tta6bl4-americas-pool"
  account_id   = var.cloudflare_account_id
  origins {
    name    = "us-east-1-origin-1"
    address = data.terraform_remote_state.us_east_1.outputs.load_balancer_dns_name
    weight  = 1.0
    enabled = true

    # Заголовки для идентификации региона
    header {
      header = "X-Region"
      values = ["us-east-1"]
    }

    header {
      header = "X-Continent"
      values = ["americas"]
    }
  }

  origins {
    name    = "us-east-1-origin-2"
    address = "us-east-1-backup.${var.x0tta6bl4_domain}"
    weight  = 0.5
    enabled = true

    header {
      header = "X-Region"
      values = ["us-east-1"]
    }

    header {
      header = "X-Continent"
      values = ["americas"]
    }
  }

  # Мониторинг состояния пула
  check_regions = ["WNAM", "ENAM"]

  # Настройки производительности
  minimum_origins = 1
  monitor        = cloudflare_load_balancer_monitor.x0tta6bl4_health_check.id
}

# Пул серверов для EMEA региона (eu-west-1)
resource "cloudflare_load_balancer_pool" "x0tta6bl4_emea_pool" {
  name         = "x0tta6bl4-emea-pool"
  account_id   = var.cloudflare_account_id
  origins {
    name    = "eu-west-1-origin-1"
    address = data.terraform_remote_state.eu_west_1.outputs.load_balancer_dns_name
    weight  = 1.0
    enabled = true

    header {
      header = "X-Region"
      values = ["eu-west-1"]
    }

    header {
      header = "X-Continent"
      values = ["emea"]
    }
  }

  origins {
    name    = "eu-west-1-origin-2"
    address = "eu-west-1-backup.${var.x0tta6bl4_domain}"
    weight  = 0.5
    enabled = true

    header {
      header = "X-Region"
      values = ["eu-west-1"]
    }

    header {
      header = "X-Continent"
      values = ["emea"]
    }
  }

  check_regions = ["WEU", "EEU"]
  minimum_origins = 1
  monitor        = cloudflare_load_balancer_monitor.x0tta6bl4_health_check.id
}

# Пул серверов для APAC региона (ap-southeast-1)
resource "cloudflare_load_balancer_pool" "x0tta6bl4_apac_pool" {
  name         = "x0tta6bl4-apac-pool"
  account_id   = var.cloudflare_account_id
  origins {
    name    = "ap-southeast-1-origin-1"
    address = data.terraform_remote_state.ap_southeast_1.outputs.load_balancer_dns_name
    weight  = 1.0
    enabled = true

    header {
      header = "X-Region"
      values = ["ap-southeast-1"]
    }

    header {
      header = "X-Continent"
      values = ["apac"]
    }
  }

  check_regions = ["APAC", "OC"]
  minimum_origins = 1
  monitor        = cloudflare_load_balancer_monitor.x0tta6bl4_health_check.id
}

# Расширенный мониторинг состояния
resource "cloudflare_load_balancer_monitor" "x0tta6bl4_health_check" {
  account_id       = var.cloudflare_account_id
  type             = "https"
  method           = "GET"
  path             = "/health"
  port             = 443
  timeout          = 5
  retries          = 3
  interval         = 60
  follow_redirects = true
  allow_insecure   = false

  # Ожидаемые коды ответа
  expected_codes = "200"

  # Дополнительные проверки
  header {
    header = "X-Health-Check"
    values = ["true"]
  }
}

# DNS записи для глобального распределения
resource "cloudflare_record" "api_record" {
  zone_id = var.cloudflare_zone_id
  name    = "api"
  type    = "CNAME"
  value   = cloudflare_load_balancer.x0tta6bl4_global_lb.hostname
  proxied = true
  ttl     = 1
}

resource "cloudflare_record" "dashboard_record" {
  zone_id = var.cloudflare_zone_id
  name    = "dashboard"
  type    = "CNAME"
  value   = cloudflare_load_balancer.x0tta6bl4_global_lb.hostname
  proxied = true
  ttl     = 1
}

resource "cloudflare_record" "quantum_record" {
  zone_id = var.cloudflare_zone_id
  name    = "quantum"
  type    = "CNAME"
  value   = cloudflare_load_balancer.x0tta6bl4_global_lb.hostname
  proxied = true
  ttl     = 1
}

# Региональные DNS записи для прямого доступа
resource "cloudflare_record" "us_east_1_record" {
  zone_id = var.cloudflare_zone_id
  name    = "us-east-1"
  type    = "CNAME"
  value   = data.terraform_remote_state.us_east_1.outputs.load_balancer_dns_name
  proxied = false
  ttl     = 300
}

resource "cloudflare_record" "eu_west_1_record" {
  zone_id = var.cloudflare_zone_id
  name    = "eu-west-1"
  type    = "CNAME"
  value   = data.terraform_remote_state.eu_west_1.outputs.load_balancer_dns_name
  proxied = false
  ttl     = 300
}

resource "cloudflare_record" "ap_southeast_1_record" {
  zone_id = var.cloudflare_zone_id
  name    = "ap-southeast-1"
  type    = "CNAME"
  value   = data.terraform_remote_state.ap_southeast_1.outputs.load_balancer_dns_name
  proxied = false
  ttl     = 300
}

# Расширенные WAF правила для глобальной защиты
resource "cloudflare_ruleset" "x0tta6bl4_global_waf" {
  zone_id = var.cloudflare_zone_id
  name    = "x0tta6bl4-global-waf-ruleset"
  kind    = "zone"
  phase   = "http_request_firewall_custom"

  rules {
    # Защита от SQL инъекций
    action = "block"
    expression = <<EOF
      (http.request.uri.path contains "union" and http.request.uri.path contains "select") or
      (http.request.uri.path contains "1=1" or http.request.uri.path contains "1 = 1") or
      (http.request.uri.path contains "script" and http.request.uri.path contains "alert") or
      (http.request.uri.path contains "xp_cmdshell" or http.request.uri.path contains "sp_executesql")
    EOF
    description = "Advanced SQL Injection Protection"
    enabled     = true
  }

  rules {
    # Защита от XSS атак
    action = "block"
    expression = <<EOF
      (http.request.uri.path contains "<script" or http.request.uri.path contains "javascript:") or
      (http.request.uri.path contains "onload=" or http.request.uri.path contains "onerror=") or
      (http.request.uri.path contains "eval(" or http.request.uri.path contains "expression(")
    EOF
    description = "Advanced XSS Protection"
    enabled     = true
  }

  rules {
    # Расширенное rate limiting для API эндпоинтов
    action = "managed_challenge"
    expression = <<EOF
      (http.request.uri.path eq "/api/v1/login" and http.rate_limit.api_login > 10) or
      (http.request.uri.path eq "/api/v1/register" and http.rate_limit.api_register > 5) or
      (http.request.uri.path ~ "/api/v1/.*" and http.rate_limit.api_general > 100)
    EOF
    description = "Advanced Rate Limiting Protection"
    enabled     = true
  }

  rules {
    # Защита от вредоносных ботов
    action = "managed_challenge"
    expression = <<EOF
      (cf.bot_management.score lt 30 and http.request.uri.path ~ ".*api.*") or
      (cf.bot_management.verified_bot eq false and http.request.uri.path ~ ".*admin.*") or
      (cf.bot_management.score lt 20 and http.request.rate gt 50)
    EOF
    description = "Advanced Bot Protection"
    enabled     = true
  }

  rules {
    # Защита от credential stuffing
    action = "block"
    expression = <<EOF
      (http.request.uri.path eq "/api/v1/login" and
       ip.src.country in {"CN" "RU" "KP" "IR"} and
       http.request.rate gt 20)
    EOF
    description = "Credential Stuffing Protection"
    enabled     = true
  }
}

# Page Rules для оптимизации глобального кеширования
resource "cloudflare_page_rule" "global_static_assets" {
  zone_id = var.cloudflare_zone_id
  target  = "*.${var.x0tta6bl4_domain}/*.css"
  priority = 10

  actions {
    cache_level         = "cache_everything"
    browser_cache_ttl   = 31536000  # 1 год
    edge_cache_ttl      = 2592000   # 30 дней
    minify {
      css  = "on"
      html = "on"
      js   = "on"
    }
    # Географическое распределение статических файлов
    cache_by_device_type = "on"
    cache_deception_armor = "on"
  }
}

resource "cloudflare_page_rule" "global_javascript_assets" {
  zone_id = var.cloudflare_zone_id
  target  = "*.${var.x0tta6bl4_domain}/*.js"
  priority = 11

  actions {
    cache_level         = "cache_everything"
    browser_cache_ttl   = 31536000
    edge_cache_ttl      = 2592000
    minify {
      js = "on"
    }
    cache_by_device_type = "on"
  }
}

resource "cloudflare_page_rule" "global_image_assets" {
  zone_id = var.cloudflare_zone_id
  target  = "*.${var.x0tta6bl4_domain}/*.jpg"
  priority = 12

  actions {
    cache_level         = "cache_everything"
    browser_cache_ttl   = 31536000
    edge_cache_ttl      = 2592000
    polish             = "lossy"
    webp               = "on"
    avif               = "on"
    mirage             = "on"
  }
}

# Cloudflare Access для админ панели
resource "cloudflare_access_application" "global_admin_panel" {
  account_id = var.cloudflare_account_id
  name       = "x0tta6bl4 Global Admin Panel"
  domain     = "admin.${var.x0tta6bl4_domain}"

  policies {
    name         = "Global Admin Access Policy"
    decision     = "allow"
    include {
      email = ["admin@${var.x0tta6bl4_domain}", "devops@${var.x0tta6bl4_domain}"]
    }
    include {
      service_token = [cloudflare_access_service_token.global_admin_token.id]
    }
  }
}

# Service Token для CI/CD систем
resource "cloudflare_access_service_token" "global_admin_token" {
  account_id = var.cloudflare_account_id
  name       = "x0tta6bl4-global-admin-token"
}

# Глобальный мониторинг и аналитика
resource "cloudflare_notification_policy" "global_cdn_alerts" {
  account_id = var.cloudflare_account_id
  name       = "x0tta6bl4 Global CDN Alerts"
  enabled    = true

  filters {
    services    = ["load_balancing", "http_requests", "spectrum"]
    status      = ["degraded", "down"]
    product     = ["load_balancer", "waf"]
  }

  mechanisms {
    email = ["alerts@${var.x0tta6bl4_domain}"]
  }
}

# Кастомные метрики для мониторинга
resource "cloudflare_ruleset" "global_custom_metrics" {
  zone_id = var.cloudflare_zone_id
  name    = "x0tta6bl4-global-custom-metrics"
  kind    = "zone"
  phase   = "http_request_transform"

  rules {
    action = "log"
    expression = "http.request.uri.path ~ \".*api.*\""
    description = "Log API requests for analytics"
    enabled = true
  }
}

# Outputs для использования в других конфигурациях
output "global_load_balancer_hostname" {
  description = "Hostname глобального load balancer'а"
  value       = cloudflare_load_balancer.x0tta6bl4_global_lb.hostname
}

output "global_load_balancer_id" {
  description = "ID глобального load balancer'а"
  value       = cloudflare_load_balancer.x0tta6bl4_global_lb.id
}

output "americas_pool_id" {
  description = "ID пула серверов для Americas региона"
  value       = cloudflare_load_balancer_pool.x0tta6bl4_americas_pool.id
}

output "emea_pool_id" {
  description = "ID пула серверов для EMEA региона"
  value       = cloudflare_load_balancer_pool.x0tta6bl4_emea_pool.id
}

output "apac_pool_id" {
  description = "ID пула серверов для APAC региона"
  value       = cloudflare_load_balancer_pool.x0tta6bl4_apac_pool.id
}

output "health_check_monitor_id" {
  description = "ID мониторинга состояния"
  value       = cloudflare_load_balancer_monitor.x0tta6bl4_health_check.id
}

output "access_service_token_id" {
  description = "ID service token для CI/CD"
  value       = cloudflare_access_service_token.global_admin_token.id
}