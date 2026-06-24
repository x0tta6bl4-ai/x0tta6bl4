{{/*
Expand the name of the chart.
*/}}
{{- define "batman-adv-optimization.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "batman-adv-optimization.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "batman-adv-optimization.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "batman-adv-optimization.labels" -}}
helm.sh/chart: {{ include "batman-adv-optimization.chart" . }}
{{ include "batman-adv-optimization.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: x0tta6bl4-infrastructure
{{- end }}

{{/*
Selector labels
*/}}
{{- define "batman-adv-optimization.selectorLabels" -}}
app.kubernetes.io/name: {{ include "batman-adv-optimization.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "batman-adv-optimization.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "batman-adv-optimization.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Generate full image name with registry
*/}}
{{- define "batman-adv-optimization.image" -}}
{{- if .Values.global.imageRegistry -}}
{{- .Values.global.imageRegistry }}/{{ .repository }}:{{ .tag }}
{{- else -}}
{{- .repository }}:{{ .tag }}
{{- end -}}
{{- end }}

{{/*
Common annotations for security and monitoring
*/}}
{{- define "batman-adv-optimization.annotations" -}}
prometheus.io/scrape: "true"
prometheus.io/port: "{{ .Values.batmanAdv.monitoring.metricsPort }}"
prometheus.io/path: "/metrics"
{{- if .Values.global.securityAnnotations }}
security.alpha.kubernetes.io/secure-compute-mode: "baseline"
{{- end }}
{{- end }}

{{/*
Regional configuration based on node location
*/}}
{{- define "batman-adv-optimization.regionalConfig" -}}
{{- $region := .Values.batmanAdv.regions | default dict }}
{{- $nodeRegion := .nodeRegion | default "us-east" }}
{{- $regionConfig := index $region $nodeRegion }}
{{- if $regionConfig }}
{{- toYaml $regionConfig }}
{{- else }}
priority: 3
gateway_nodes: 1
backup_paths: 1
{{- end }}
{{- end }}

{{/*
Multi-path configuration template
*/}}
{{- define "batman-adv-optimization.multipathConfig" -}}
{{- if .Values.batmanAdv.config.multipath.enabled }}
multipath_mode {{ .Values.batmanAdv.config.multipath.enabled | ternary 1 0 }}
multipath_max_paths {{ .Values.batmanAdv.config.multipath.maxPaths }}
multipath_path_discovery 1
{{- end }}
{{- end }}

{{/*
AODV fallback configuration template
*/}}
{{- define "batman-adv-optimization.aodvConfig" -}}
{{- if .Values.batmanAdv.config.aodv.enabled }}
aodv_fallback_timeout {{ .Values.batmanAdv.config.aodv.fallbackTimeout | replace "s" "" | int }}000
aodv_max_retries {{ .Values.batmanAdv.config.aodv.routeRequestRetries }}
aodv_rate_limit {{ .Values.batmanAdv.config.aodv.routeRequestRateLimit | replace "/s" "" }}
{{- end }}
{{- end }}