{{/*
Expand the chart name.
*/}}
{{- define "maas-event-store.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a fully qualified app name.
*/}}
{{- define "maas-event-store.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Chart label.
*/}}
{{- define "maas-event-store.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels.
*/}}
{{- define "maas-event-store.labels" -}}
helm.sh/chart: {{ include "maas-event-store.chart" . }}
app.kubernetes.io/name: {{ include "maas-event-store.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Selector labels.
*/}}
{{- define "maas-event-store.selectorLabels" -}}
app.kubernetes.io/name: {{ include "maas-event-store.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
ServiceAccount name.
*/}}
{{- define "maas-event-store.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "maas-event-store.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/*
PostgreSQL service hostname.
Matches common Bitnami naming: <release>-postgresql.
*/}}
{{- define "maas-event-store.postgresql.fullname" -}}
{{- printf "%s-postgresql" .Release.Name -}}
{{- end -}}

{{/*
MongoDB service hostname.
Matches common Bitnami naming: <release>-mongodb.
*/}}
{{- define "maas-event-store.mongodb.fullname" -}}
{{- printf "%s-mongodb" .Release.Name -}}
{{- end -}}

{{/*
PostgreSQL secret name.
*/}}
{{- define "maas-event-store.postgresql.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{- .Values.secrets.existingSecret -}}
{{- else -}}
{{- printf "%s-postgresql" .Release.Name -}}
{{- end -}}
{{- end -}}

{{/*
MongoDB secret name.
*/}}
{{- define "maas-event-store.mongodb.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{- .Values.secrets.existingSecret -}}
{{- else -}}
{{- printf "%s-mongodb" .Release.Name -}}
{{- end -}}
{{- end -}}
