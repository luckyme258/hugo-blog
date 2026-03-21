# 确保目录存在
mkdir layouts\_default -Force

# 用正确的方式创建模板（注意：要用英文引号）
@'
{{ define "main" }}
<h1>📚 归档</h1>

{{ $pages := where .Site.RegularPages "Draft" false }}
{{ range $pages.GroupByDate "2006年01月" }}
  <h2>{{ .Key }}</h2>
  <ul>
    {{ range .Pages }}
    <li>
      <span>{{ .Date.Format "2006-01-02" }}</span>
      <a href="{{ .RelPermalink }}">{{ .Title }}</a>
    </li>
    {{ end }}
  </ul>
{{ end }}

{{ if eq (len $pages) 0 }}
  <p>还没有文章，写第一篇吧！</p>
{{ end }}
{{ end }}
'@ | Out-File -FilePath layouts\_default\archives.html -Encoding utf8