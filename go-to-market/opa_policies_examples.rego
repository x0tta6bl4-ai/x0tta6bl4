package x0tta6bl4.mesh

# Политика 1: Разрешение регистрации узла при условии предъявления валидного SPIFFE ID и отсутствия блокировки.
allow_node_registration[node_id] {
  input.action == "register"
  node_id := input.node.id
  startswith(input.node.spiffe_id, "spiffe://x0tta6bl4/")
  not blocked[node_id]
}

blocked[node_id] {
  some node_id
  node_id == input.node.id
  input.node.id in input.blocklist
}

# Политика 2: Уровень доверия (trust_level) определяется типом узла и историей отказов.
trust_level = level {
  failures := input.node.metrics.failures_last_24h
  role := input.node.role
  level := "low"
  role == "edge"
  failures > 5
} else = level {
  role := input.node.role
  level := "medium"
  role == "edge"
} else = level {
  role := input.node.role
  level := "high"
  role == "core"
}

# Политика 3: Лимиты пропускной способности (rate limit) в зависимости от trust_level.
rate_limit = rl {
  trust := trust_level
  rl := 50
  trust == "low"
} else = rl {
  trust := trust_level
  rl := 200
  trust == "medium"
} else = rl {
  trust := trust_level
  rl := 500
  trust == "high"
}

# Политика 4: Аудит всех действий высокого риска (например, смена конфигурации). Запись в журнал.
log_audit_entry = entry {
  input.action == "config_change"
  entry := {
    "timestamp": input.timestamp,
    "actor": input.actor.id,
    "node": input.node.id,
    "change": input.change_id,
    "severity": "high"
  }
}

# Политика 5: Запрет маршрутизации через узлы с trust_level == low для критичных пакетов.
deny_routing[reason] {
  input.action == "route_packet"
  input.packet.critical == true
  trust_level == "low"
  reason := sprintf("critical packet cannot route via low trust node %v", [input.node.id])
}
