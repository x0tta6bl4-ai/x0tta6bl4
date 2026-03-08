{{/*
Expand the name of the chart.
*/}}
{{- define "x0tta-mesh-operator.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "x0tta-mesh-operator.fullname" -}}
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
Create chart label.
*/}}
{{- define "x0tta-mesh-operator.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "x0tta-mesh-operator.labels" -}}
helm.sh/chart: {{ include "x0tta-mesh-operator.chart" . }}
{{ include "x0tta-mesh-operator.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: x0tta6bl4-mesh
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "x0tta-mesh-operator.selectorLabels" -}}
app.kubernetes.io/name: {{ include "x0tta-mesh-operator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
ServiceAccount name.
*/}}
{{- define "x0tta-mesh-operator.serviceAccountName" -}}
{{- if .Values.operator.serviceAccount.create }}
{{- default (include "x0tta-mesh-operator.fullname" .) .Values.operator.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.operator.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Leader election namespace.
*/}}
{{- define "x0tta-mesh-operator.leaderElectionNamespace" -}}
{{- default .Release.Namespace .Values.leaderElection.namespace }}
{{- end }}

{{/*
Webhook service name.
*/}}
{{- define "x0tta-mesh-operator.webhookServiceName" -}}
{{- printf "%s-webhook-service" (include "x0tta-mesh-operator.fullname" .) -}}
{{- end }}

{{/*
Webhook certificate secret name.
*/}}
{{- define "x0tta-mesh-operator.webhookSecretName" -}}
{{- if .Values.operator.webhook.tls.secretName -}}
{{- .Values.operator.webhook.tls.secretName -}}
{{- else -}}
{{- printf "%s-webhook-server-cert" (include "x0tta-mesh-operator.fullname" .) -}}
{{- end -}}
{{- end }}

{{/*
Webhook certificate resource name.
*/}}
{{- define "x0tta-mesh-operator.webhookCertificateName" -}}
{{- printf "%s-webhook-cert" (include "x0tta-mesh-operator.fullname" .) -}}
{{- end }}

{{/*
Webhook issuer name.
*/}}
{{- define "x0tta-mesh-operator.webhookIssuerName" -}}
{{- if .Values.operator.webhook.certManager.issuerRef.name -}}
{{- .Values.operator.webhook.certManager.issuerRef.name -}}
{{- else -}}
{{- printf "%s-webhook-selfsigned" (include "x0tta-mesh-operator.fullname" .) -}}
{{- end -}}
{{- end }}
