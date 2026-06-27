{{/*
Expand the name of the chart.
*/}}
{{- define "x0tta6bl4.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "x0tta6bl4.fullname" -}}
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
{{- define "x0tta6bl4.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "x0tta6bl4.labels" -}}
helm.sh/chart: {{ include "x0tta6bl4.chart" . }}
{{ include "x0tta6bl4.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/component: mesh-node
app.kubernetes.io/part-of: x0tta6bl4
{{- end }}

{{/*
Selector labels
*/}}
{{- define "x0tta6bl4.selectorLabels" -}}
app.kubernetes.io/name: {{ include "x0tta6bl4.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "x0tta6bl4.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "x0tta6bl4.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Zero Trust configuration
*/}}
{{- define "x0tta6bl4.zeroTrustConfig" -}}
zkp:
  enabled: {{ .Values.zeroTrust.zkp.enabled }}
  algorithm: {{ .Values.zeroTrust.zkp.algorithm }}
postQuantum:
  enabled: {{ .Values.zeroTrust.postQuantum.enabled }}
  algorithm: {{ .Values.zeroTrust.postQuantum.algorithm }}
deviceAttestation:
  enabled: {{ .Values.zeroTrust.deviceAttestation.enabled }}
  privacyPreserving: {{ .Values.zeroTrust.deviceAttestation.privacyPreserving }}
did:
  enabled: {{ .Values.zeroTrust.did.enabled }}
  method: {{ .Values.zeroTrust.did.method }}
policyEngine:
  enabled: {{ .Values.zeroTrust.policyEngine.enabled }}
  defaultEffect: {{ .Values.zeroTrust.policyEngine.defaultEffect }}
continuousVerification:
  enabled: {{ .Values.zeroTrust.continuousVerification.enabled }}
  baseInterval: {{ .Values.zeroTrust.continuousVerification.baseIntervalSeconds }}
autoIsolation:
  enabled: {{ .Values.zeroTrust.autoIsolation.enabled }}
threatIntelligence:
  enabled: {{ .Values.zeroTrust.threatIntelligence.enabled }}
{{- end }}

{{/*
SPIFFE Trust Domain
*/}}
{{- define "x0tta6bl4.trustDomain" -}}
{{- .Values.spiffe.trustDomain | default "x0tta6bl4.mesh" }}
{{- end }}
