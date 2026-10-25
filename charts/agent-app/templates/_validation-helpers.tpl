{{/* Runtime guards remain useful with --skip-schema-validation. Never echo values. */}}
{{- define "agent-app.integer" -}}
{{- if not (and (has (kindOf .value) (list "int" "int64" "float64" "float32")) (regexMatch "^[0-9]+$" (toString .value))) -}}
{{- fail (printf "agent-app: %s must be an integer; use an unquoted whole number." .path) -}}
{{- end -}}
{{- if or (lt (float64 .value) (float64 .min)) (gt (float64 .value) (float64 .max)) -}}
{{- fail (printf "agent-app: %s must be between %v and %v." .path .min .max) -}}
{{- end -}}
{{- end -}}

{{- define "agent-app.dnsName" -}}
{{- if not (kindIs "string" .value) -}}
{{- fail (printf "agent-app: %s must be a DNS name string." .path) -}}
{{- end -}}
{{- if and (not (and .optional (eq .value ""))) (or (gt (len .value) 253) (not (regexMatch "^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$" .value))) -}}
{{- fail (printf "agent-app: %s must be a DNS name; use lower-case letters, digits, hyphens and dots." .path) -}}
{{- end -}}
{{- range splitList "." .value -}}
{{- if gt (len .) 63 -}}{{- fail (printf "agent-app: %s DNS labels must be at most 63 characters." $.path) -}}{{- end -}}
{{- end -}}
{{- end -}}

{{- define "agent-app.stringMapGuard" -}}
{{- if not (kindIs "map" .value) -}}{{- fail (printf "agent-app: %s must be a map of strings." .path) -}}{{- end -}}
{{- range $key, $value := .value -}}
{{- if not (kindIs "string" $value) -}}{{- fail (printf "agent-app: %s values must be strings; quote YAML scalars." $.path) -}}{{- end -}}
{{- end -}}
{{- end -}}
