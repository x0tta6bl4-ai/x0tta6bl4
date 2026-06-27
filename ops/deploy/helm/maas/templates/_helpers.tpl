{{/*
MaaS Helm Chart - Helper Templates
==================================
*/}}

{{/*
Expand the name of the chart.
*/}}
{{- define "maas.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "maas.fullname" -}}
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
{{- define "maas.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "maas.labels" -}}
helm.sh/chart: {{ include "maas.chart" . }}
{{ include "maas.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- if .Values.global.environment }}
environment: {{ .Values.global.environment }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "maas.selectorLabels" -}}
app.kubernetes.io/name: {{ include "maas.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
API component labels
*/}}
{{- define "maas.api.labels" -}}
{{ include "maas.labels" . }}
app.kubernetes.io/component: api
{{- end }}

{{- define "maas.api.selectorLabels" -}}
{{ include "maas.selectorLabels" . }}
app.kubernetes.io/component: api
{{- end }}

{{/*
Controller component labels
*/}}
{{- define "maas.controller.labels" -}}
{{ include "maas.labels" . }}
app.kubernetes.io/component: controller
{{- end }}

{{- define "maas.controller.selectorLabels" -}}
{{ include "maas.selectorLabels" . }}
app.kubernetes.io/component: controller
{{- end }}

{{/*
Worker component labels
*/}}
{{- define "maas.worker.labels" -}}
{{ include "maas.labels" . }}
app.kubernetes.io/component: worker
{{- end }}

{{- define "maas.worker.selectorLabels" -}}
{{ include "maas.selectorLabels" . }}
app.kubernetes.io/component: worker
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "maas.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "maas.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Return the proper API image name
*/}}
{{- define "maas.api.image" -}}
{{- $registryName := .Values.api.image.registry | default .Values.global.imageRegistry -}}
{{- $repositoryName := .Values.api.image.repository -}}
{{- $tag := .Values.api.image.tag | default .Chart.AppVersion | toString -}}
{{- if $registryName }}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- else }}
{{- printf "%s:%s" $repositoryName $tag -}}
{{- end }}
{{- end }}

{{/*
Return the proper Controller image name
*/}}
{{- define "maas.controller.image" -}}
{{- $registryName := .Values.controller.image.registry | default .Values.global.imageRegistry -}}
{{- $repositoryName := .Values.controller.image.repository -}}
{{- $tag := .Values.controller.image.tag | default .Chart.AppVersion | toString -}}
{{- if $registryName }}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- else }}
{{- printf "%s:%s" $repositoryName $tag -}}
{{- end }}
{{- end }}

{{/*
Return the proper Worker image name
*/}}
{{- define "maas.worker.image" -}}
{{- $registryName := .Values.worker.image.registry | default .Values.global.imageRegistry -}}
{{- $repositoryName := .Values.worker.image.repository -}}
{{- $tag := .Values.worker.image.tag | default .Chart.AppVersion | toString -}}
{{- if $registryName }}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- else }}
{{- printf "%s:%s" $repositoryName $tag -}}
{{- end }}
{{- end }}

{{/*
Return the appropriate apiVersion for ingress
*/}}
{{- define "maas.ingress.apiVersion" -}}
{{- if semverCompare ">=1.19-0" .Capabilities.KubeVersion.GitVersion -}}
networking.k8s.io/v1
{{- else if semverCompare ">=1.14-0" .Capabilities.KubeVersion.GitVersion -}}
networking.k8s.io/v1beta1
{{- else -}}
extensions/v1beta1
{{- end }}
{{- end }}

{{/*
Return the appropriate apiVersion for HPA
*/}}
{{- define "maas.hpa.apiVersion" -}}
{{- if semverCompare ">=1.23-0" .Capabilities.KubeVersion.GitVersion -}}
autoscaling/v2
{{- else -}}
autoscaling/v2beta2
{{- end }}
{{- end }}

{{/*
Create annotations for pods
*/}}
{{- define "maas.podAnnotations" -}}
{{- if .Values.podAnnotations }}
{{- toYaml .Values.podAnnotations }}
{{- end }}
prometheus.io/scrape: "true"
prometheus.io/port: "{{ .Values.api.service.targetPort }}"
prometheus.io/path: "/metrics"
{{- end }}

{{/*
Pod anti-affinity template
*/}}
{{- define "maas.podAntiAffinity" -}}
{{- if .Values.podAntiAffinity.enabled }}
podAntiAffinity:
  preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        labelSelector:
          matchLabels:
            {{- include "maas.selectorLabels" . | nindent 10 }}
        topologyKey: {{ .Values.podAntiAffinity.topologyKey }}
{{- end }}
{{- end }}

{{/*
Database connection string
*/}}
{{- define "maas.databaseUrl" -}}
{{- $host := printf "%s-postgresql.%s.svc.cluster.local" (include "maas.fullname" .) .Release.Namespace -}}
{{- $port := 5432 -}}
{{- $user := .Values.postgresql.auth.username -}}
{{- $password := .Values.postgresql.auth.password -}}
{{- $database := .Values.postgresql.auth.database -}}
{{- printf "postgresql://%s:%s@%s:%d/%s" $user $password $host $port $database -}}
{{- end }}

{{/*
Redis connection string
*/}}
{{- define "maas.redisUrl" -}}
{{- $host := printf "%s-redis-master.%s.svc.cluster.local" (include "maas.fullname" .) .Release.Namespace -}}
{{- $port := 6379 -}}
{{- $password := .Values.redis.auth.password -}}
{{- printf "redis://:%s@%s:%d/0" $password $host $port -}}
{{- end }}
