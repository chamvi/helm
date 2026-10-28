{{- define "agent-app.validateModels" -}}
{{- $v := .Values -}}
{{- if not (kindIs "string" $v.model) -}}{{- fail "agent-app: model must be a provider/model-id string." -}}{{- end -}}
{{- if and $v.model (not (regexMatch "^[a-z0-9]+(-[a-z0-9]+)*/[^[:space:]]+$" $v.model)) -}}{{- fail "agent-app: model must be a provider/model-id string." -}}{{- end -}}
{{- if not (kindIs "map" $v.providers) -}}{{- fail "agent-app: providers must be a map of named providers." -}}{{- end -}}
{{- range $name, $provider := $v.providers -}}
{{- if or (gt (len $name) 64) (not (regexMatch "^[a-z0-9]+(-[a-z0-9]+)*$" $name)) -}}{{- fail "agent-app: providers names must be lower-kebab names of at most 64 characters." -}}{{- end -}}
{{- if not (kindIs "map" $provider) -}}{{- fail "agent-app: providers entries must be objects." -}}{{- end -}}
{{- range $field, $_ := $provider -}}
{{- if not (has $field (list "type" "baseURL" "apiKey" "headers")) -}}{{- fail "agent-app: providers entries accept only type, baseURL, apiKey and headers." -}}{{- end -}}
{{- end -}}
{{- if not (has $provider.type (list "anthropic" "openai" "openai-compatible" "google" "mistral" "xai" "gateway")) -}}{{- fail "agent-app: providers type must name a supported provider type." -}}{{- end -}}
{{- if and (eq $provider.type "openai-compatible") (not $provider.baseURL) -}}{{- fail "agent-app: providers with type openai-compatible require baseURL." -}}{{- end -}}
{{- if hasKey $provider "baseURL" -}}
{{- if not (kindIs "string" $provider.baseURL) -}}{{- fail "agent-app: providers baseURL must be an absolute http(s) URL without credentials, query or fragment." -}}{{- end -}}
{{- if not (regexMatch "^https?://([A-Za-z0-9.-]+|\\[[0-9A-Fa-f:.]+\\])(:[0-9]{1,5})?(/[^?#@[:space:]]*)?$" $provider.baseURL) -}}{{- fail "agent-app: providers baseURL must be an absolute http(s) URL without credentials, query or fragment." -}}{{- end -}}
{{- end -}}
{{- if hasKey $provider "apiKey" -}}
{{- $key := $provider.apiKey -}}
{{- if not (kindIs "map" $key) -}}{{- fail "agent-app: providers apiKey must be a secretName/key reference, never a literal credential." -}}{{- end -}}
{{- if or (ne (len $key) 2) (not (kindIs "string" $key.secretName)) (not (kindIs "string" $key.key)) -}}{{- fail "agent-app: providers apiKey requires only secretName and key strings." -}}{{- end -}}
{{- include "agent-app.dnsName" (dict "value" $key.secretName "path" "providers.apiKey.secretName") -}}
{{- if not (regexMatch "^[A-Za-z0-9._-]+$" $key.key) -}}{{- fail "agent-app: providers apiKey.key must be a Secret data key." -}}{{- end -}}
{{- end -}}
{{- if hasKey $provider "headers" -}}
{{- if not (kindIs "map" $provider.headers) -}}{{- fail "agent-app: providers headers must be a map." -}}{{- end -}}
{{- range $header, $setting := $provider.headers -}}
{{- if not (regexMatch "^[a-z0-9]+(-[a-z0-9]+)*$" $header) -}}{{- fail "agent-app: providers header names must be lower-kebab names." -}}{{- end -}}
{{- if not (kindIs "map" $setting) -}}{{- fail "agent-app: providers headers require value or valueFrom.secretKeyRef." -}}{{- end -}}
{{- if ne (len $setting) 1 -}}{{- fail "agent-app: providers headers require exactly one of value or valueFrom.secretKeyRef." -}}{{- end -}}
{{- if hasKey $setting "value" -}}
{{- if or (not (kindIs "string" $setting.value)) (regexMatch "(?i)authorization|api[-_]?key|token|secret|auth" $header) -}}{{- fail "agent-app: providers credential headers require valueFrom.secretKeyRef, never a literal value." -}}{{- end -}}
{{- else -}}
{{- if not (kindIs "map" $setting.valueFrom) -}}{{- fail "agent-app: providers headers require valueFrom.secretKeyRef." -}}{{- end -}}
{{- if or (ne (len $setting.valueFrom) 1) (not (kindIs "map" $setting.valueFrom.secretKeyRef)) -}}{{- fail "agent-app: providers headers require only valueFrom.secretKeyRef." -}}{{- end -}}
{{- $key := $setting.valueFrom.secretKeyRef -}}
{{- if or (ne (len $key) 2) (not (kindIs "string" $key.name)) (not (kindIs "string" $key.key)) -}}{{- fail "agent-app: providers header secretKeyRef requires name and key strings." -}}{{- end -}}
{{- include "agent-app.dnsName" (dict "value" $key.name "path" "providers.headers.valueFrom.secretKeyRef.name") -}}
{{- if not (regexMatch "^[A-Za-z0-9._-]+$" $key.key) -}}{{- fail "agent-app: providers header secretKeyRef.key must be a Secret data key." -}}{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- $names := include "agent-app.ownedEnv" . | fromJsonArray -}}
{{- if ne (len $names) (len (uniq $names)) -}}{{- fail "agent-app: providers and header names must not generate duplicate environment variable names; rename a provider or header." -}}{{- end -}}
{{- end -}}
