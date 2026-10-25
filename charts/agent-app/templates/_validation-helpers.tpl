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

{{/* "true" for an IPv4 CIDR with octets 0 to 255, else empty. */}}
{{- define "agent-app.isIPv4CIDR" -}}
{{- if regexMatch "^([0-9]{1,3}\\.){3}[0-9]{1,3}/([0-9]|[12][0-9]|3[0-2])$" . -}}
{{- $ok := true -}}
{{- range splitList "." (first (splitList "/" .)) -}}{{- if gt (int .) 255 -}}{{- $ok = false -}}{{- end -}}{{- end -}}
{{- if $ok -}}true{{- end -}}
{{- end -}}
{{- end -}}

{{/* "true" for an IPv6 CIDR (hex groups, at most one ::, prefix 0 to 128), else empty. */}}
{{- define "agent-app.isIPv6CIDR" -}}
{{- if and (regexMatch "^(?i)([0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}/([0-9]|[1-9][0-9]|1[01][0-9]|12[0-8])$" .) (le (len (splitList "::" .)) 2) -}}true{{- end -}}
{{- end -}}
