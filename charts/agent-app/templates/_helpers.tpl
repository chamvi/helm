{{- define "agent-app.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "agent-app.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride -}}
{{- else -}}
{{- $name := include "agent-app.name" . -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "agent-app.componentName" -}}
{{- $max := default 63 .max | int -}}
{{- $budget := sub $max (add1 (len .suffix)) | int -}}
{{- $base := include "agent-app.fullname" .context -}}
{{- if gt (len $base) $budget -}}
{{/* Hash the pair, not the truncated prefix: differing suffix lengths can otherwise collide. */}}
{{- $hash := toJson (list $base .suffix) | sha256sum | trunc 10 -}}
{{- $prefixBudget := sub $budget 11 | int -}}
{{- printf "%s-%s-%s" ($base | trunc $prefixBudget | trimSuffix "-") $hash .suffix -}}
{{- else -}}
{{- printf "%s-%s" $base .suffix -}}
{{- end -}}
{{- end -}}

{{- define "agent-app.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "agent-app.selectorLabels" -}}
app.kubernetes.io/name: {{ include "agent-app.name" .context | quote }}
app.kubernetes.io/instance: {{ .context.Release.Name | quote }}
app.kubernetes.io/component: {{ .component | quote }}
{{- end -}}

{{- define "agent-app.labels" -}}
helm.sh/chart: {{ include "agent-app.chart" .context | quote }}
{{ include "agent-app.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .context.Release.Service | quote }}
{{- end -}}

{{/* Quote both keys and values: YAML boolean and numeric labels stay strings. */}}
{{- define "agent-app.stringMap" -}}
{{- range $key, $value := . }}
{{ $key | quote }}: {{ $value | quote }}
{{- end -}}
{{- end -}}

{{- define "agent-app.image" -}}
{{- if .Values.image.digest -}}
{{- printf "%s@%s" .Values.image.repository .Values.image.digest -}}
{{- else -}}
{{- printf "%s:%s" .Values.image.repository .Values.image.tag -}}
{{- end -}}
{{- end -}}

{{- define "agent-app.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "agent-app.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "agent-app.basePath" -}}{{ .Values.basePath }}{{- end -}}

{{/* Only the origin: approvalUrlOf adds CHAMVI_BASE_PATH exactly once. */}}
{{- define "agent-app.publicUrl" -}}
{{- printf "%s://%s" (ternary "https" "http" (ne .Values.ingress.tls.secretName "")) .Values.ingress.host -}}
{{- end -}}

{{- define "agent-app.ownedEnv" -}}
{{- $names := list "PORT" "CHAMVI_BASE_PATH" -}}
{{- if .Values.model -}}{{- $names = append $names "CHAMVI_MODEL" -}}{{- end -}}
{{- range $name, $provider := .Values.providers -}}
{{- $prefix := printf "CHAMVI_PROVIDER_%s_" ($name | upper | replace "-" "_") -}}
{{- $names = append $names (printf "%sTYPE" $prefix) -}}
{{- if $provider.baseURL -}}{{- $names = append $names (printf "%sBASE_URL" $prefix) -}}{{- end -}}
{{- if $provider.apiKey -}}{{- $names = append $names (printf "%sAPI_KEY" $prefix) -}}{{- end -}}
{{- range $header, $_ := $provider.headers -}}{{- $names = append $names (printf "%sHEADER_%s" $prefix ($header | upper | replace "-" "_")) -}}{{- end -}}
{{- end -}}
{{- if .Values.cronJobs -}}{{- $names = append $names "CHAMVI_SCHEDULER" -}}{{- end -}}
{{- if .Values.sandbox.enabled -}}{{- $names = append $names "CHAMVI_SANDBOX_NAMESPACE" -}}{{- end -}}
{{- toJson $names -}}
{{- end -}}

{{/* Values files and Flux pass numbers as float64, which toString and plain rendering print as 1.2e+06; toJson keeps 1200000. */}}
{{- define "agent-app.scalar" -}}
{{- if or (kindIs "float64" .) (kindIs "float32" .) -}}{{- toJson . -}}{{- else -}}{{- toString . -}}{{- end -}}
{{- end -}}

{{- define "agent-app.env" -}}
{{- if .Values.model }}
- name: CHAMVI_MODEL
  value: {{ .Values.model | quote }}
{{- end }}
{{- range $name, $provider := .Values.providers }}
{{- $prefix := printf "CHAMVI_PROVIDER_%s_" ($name | upper | replace "-" "_") }}
- name: {{ printf "%sTYPE" $prefix }}
  value: {{ $provider.type | quote }}
{{- if $provider.baseURL }}
- name: {{ printf "%sBASE_URL" $prefix }}
  value: {{ $provider.baseURL | quote }}
{{- end }}
{{- if $provider.apiKey }}
- name: {{ printf "%sAPI_KEY" $prefix }}
  valueFrom:
    secretKeyRef:
      name: {{ $provider.apiKey.secretName | quote }}
      key: {{ $provider.apiKey.key | quote }}
{{- end }}
{{- range $header, $setting := $provider.headers }}
- name: {{ printf "%sHEADER_%s" $prefix ($header | upper | replace "-" "_") }}
{{- if hasKey $setting "value" }}
  value: {{ $setting.value | quote }}
{{- else }}
  valueFrom: {{ $setting.valueFrom | toJson }}
{{- end }}
{{- end }}
{{- end }}
- name: PORT
  value: "3000"
- name: CHAMVI_BASE_PATH
  value: {{ include "agent-app.basePath" . | quote }}
{{- if .Values.cronJobs }}
- name: CHAMVI_SCHEDULER
  value: "false"
{{- end }}
{{- if .Values.sandbox.enabled }}
- name: CHAMVI_SANDBOX_NAMESPACE
  value: {{ .Values.sandbox.namespace | quote }}
{{- end }}
{{- $derivePublicUrl := and .Values.ingress.enabled (or (not (hasKey .Values.env "CHAMVI_PUBLIC_URL")) (eq (toString .Values.env.CHAMVI_PUBLIC_URL) "")) }}
{{- if $derivePublicUrl }}
- name: CHAMVI_PUBLIC_URL
  value: {{ include "agent-app.publicUrl" . | quote }}
{{- end }}
{{- $deriveDeployment := and .Values.sandbox.enabled (or (not (hasKey .Values.env "CHAMVI_DEPLOYMENT")) (eq (toString .Values.env.CHAMVI_DEPLOYMENT) "")) }}
{{- if $deriveDeployment }}
- name: CHAMVI_DEPLOYMENT
  value: {{ include "agent-app.fullname" . | quote }}
{{- end }}
{{- range $key, $value := .Values.env }}
{{- if not (or (and $derivePublicUrl (eq $key "CHAMVI_PUBLIC_URL")) (and $deriveDeployment (eq $key "CHAMVI_DEPLOYMENT"))) }}
- name: {{ $key | quote }}
  value: {{ include "agent-app.scalar" $value | quote }}
{{- end }}
{{- end -}}
{{- end -}}

{{- define "agent-app.envFrom" -}}
{{- range .Values.secrets }}
- secretRef:
    name: {{ . | quote }}
{{- end -}}
{{- end -}}

{{- define "agent-app.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: 1000
runAsGroup: 1000
fsGroup: 1000
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "agent-app.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: [ALL]
{{- end -}}

{{/* A test hook never receives the app's token, credentials or workload env. */}}
{{- define "agent-app.podCommon" -}}
serviceAccountName: {{ include "agent-app.serviceAccountName" .context | quote }}
automountServiceAccountToken: {{ and (not .test) .context.Values.sandbox.enabled }}
securityContext:
  {{- include "agent-app.podSecurityContext" .context | nindent 2 }}
terminationGracePeriodSeconds: {{ include "agent-app.scalar" .context.Values.terminationGracePeriodSeconds }}
{{- with .context.Values.imagePullSecrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
volumes:
  - name: tmp
    emptyDir: {}
{{- with .context.Values.nodeSelector }}
nodeSelector:
  {{- include "agent-app.stringMap" . | nindent 2 }}
{{- end }}
{{- with .context.Values.tolerations }}
tolerations:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .context.Values.affinity }}
affinity:
  {{- toYaml . | nindent 2 }}
{{- end -}}
{{- end -}}

{{- define "agent-app.containerCommon" -}}
image: {{ include "agent-app.image" .context | quote }}
imagePullPolicy: {{ .context.Values.image.pullPolicy }}
securityContext:
  {{- include "agent-app.containerSecurityContext" .context | nindent 2 }}
volumeMounts:
  - name: tmp
    mountPath: /tmp
{{- if not .test }}
env:
  {{- include "agent-app.env" .context | nindent 2 }}
{{- if .context.Values.secrets }}
envFrom:
  {{- include "agent-app.envFrom" .context | nindent 2 }}
{{- end }}
{{- end -}}
{{- end -}}
