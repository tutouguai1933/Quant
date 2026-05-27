# Grafana Monitoring Setup

This document describes how to set up and use the Grafana monitoring dashboard for the Quant trading system.

## Architecture

The monitoring stack consists of:

- **Prometheus** (port 9091): Metrics collection and storage
- **Grafana** (port 3000): Visualization and dashboards
- **cAdvisor** (port 8080): Docker container metrics
- **Node Exporter** (port 9100): System-level metrics

## Quick Start

### 1. Start the Monitoring Stack

```bash
cd infra/deploy
docker-compose up -d prometheus grafana cadvisor node-exporter
```

### 2. Access Grafana

Open your browser and navigate to:
```
http://localhost:3000
```

Default credentials:
- Username: `admin`
- Password: `admin123` (can be changed via `QUANT_GRAFANA_ADMIN_PASSWORD` env var)

### 3. View the Dashboard

The "Quant Trading Overview" dashboard is automatically provisioned. Navigate to:
- Dashboards > Quant > Quant Trading Overview

## Dashboard Panels

### API Performance Section

| Panel | Description | Metrics |
|-------|-------------|---------|
| API Request Latency | Request latency over time (P50/P95/P99) | `http_request_duration_seconds_bucket` |
| API Error Rate | Current error rate percentage | `http_requests_total{status=~"5.."}` |
| API Throughput | Requests per second by endpoint | `http_requests_total` |

### Trading Status Section

| Panel | Description | Metrics |
|-------|-------------|---------|
| Open Positions | Current open position count | `freqtrade_open_positions` |
| Total P&L | Total profit/loss in USD | `freqtrade_total_profit` |
| Win Rate | Win ratio percentage | `freqtrade_win_ratio` |
| Daily Profit Trend | Daily profit over time | `freqtrade_daily_profit` |

### Service Health Section

| Panel | Description | Metrics |
|-------|-------------|---------|
| Container Status | Status table of all containers | `container_status` |
| Container CPU Usage | CPU usage per container | `container_cpu_usage_seconds_total` |
| Container Memory Usage | Memory usage per container | `container_memory_usage_bytes` |

### Alert History Section

| Panel | Description | Metrics |
|-------|-------------|---------|
| Alert Level Distribution | Pie chart of alerts by level | `alerts_total` |
| Alerts per Hour | Alert frequency over time | `increase(alerts_total[1h])` |
| Escalation History | Escalation count table | `alert_escalation_count` |
| Active Alerts Summary | Current active alerts by level | `alert_active_count` |

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `QUANT_GRAFANA_ADMIN_USER` | Grafana admin username | `admin` |
| `QUANT_GRAFANA_ADMIN_PASSWORD` | Grafana admin password | `admin123` |
| `QUANT_PROMETHEUS_CONTAINER_NAME` | Prometheus container name | `quant-prometheus` |
| `QUANT_GRAFANA_CONTAINER_NAME` | Grafana container name | `quant-grafana` |

### Prometheus Scraping Targets

The Prometheus configuration scrapes metrics from:

1. **Prometheus itself** (localhost:9091)
2. **Quant API** (port 9011) - exposes a lightweight `/metrics` endpoint
3. **Node Exporter** (port 9100) - System metrics

cAdvisor remains in `infra/deploy/docker-compose.yml`, but it is not scraped by default until the server has the cAdvisor image and container running. After deployment, enable the commented cAdvisor job in `infra/prometheus/prometheus.yml` only when `http://localhost:8080/healthz` is healthy.

Freqtrade REST runs on port 9013, but it is not scraped by the default Prometheus config because its credentials are private and must stay in `infra/freqtrade/user_data/config.private.json` / deployment environment files.

### Data Retention

- Prometheus retains metrics for **15 days** by default
- Configure via `--storage.tsdb.retention.time` flag

## API Metrics Endpoint

The API currently exposes lightweight process metrics at `/metrics`. Add richer counters and histograms later only after approving the required dependency change.

## Alerting Rules

### Recommended Alert Rules

Create alert rules in Prometheus for critical conditions:

```yaml
groups:
  - name: quant_alerts
    rules:
      # API latency alert
      - alert: HighAPILatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API latency detected"
          description: "P95 latency exceeds 500ms"

      # Container health alert
      - alert: ContainerDown
        expr: container_status{status!="running"} == 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Container {{ $labels.container }} is down"

      # High error rate alert
      - alert: HighErrorRate
        expr: sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API error rate"
          description: "Error rate exceeds 5%"
```

## Troubleshooting

### Grafana Not Loading Dashboard

1. Check that dashboard files exist in `infra/grafana/dashboards/`
2. Verify provisioning configuration in `infra/grafana/provisioning/`
3. Restart Grafana: `docker-compose restart grafana`

### Prometheus Not Collecting Metrics

1. Check Prometheus targets: `http://localhost:9091/targets`
2. Verify API `/metrics` endpoint is accessible
3. Verify Node Exporter is listening on `http://localhost:9100/metrics`

### No Container Metrics

1. Ensure cAdvisor is running: `docker ps | grep cadvisor`
2. Check cAdvisor health: `curl http://localhost:8080/healthz`
3. Enable the commented cAdvisor scrape job in `infra/prometheus/prometheus.yml`

## File Locations

| File | Purpose |
|------|---------|
| `infra/grafana/dashboards/quant-overview.json` | Main dashboard definition |
| `infra/grafana/provisioning/datasources/prometheus.yml` | Prometheus datasource config |
| `infra/grafana/provisioning/dashboards/dashboards.yml` | Dashboard provisioning config |
| `infra/prometheus/prometheus.yml` | Prometheus scrape config |
| `infra/deploy/docker-compose.yml` | Container orchestration |

## Port Mapping

| Service | Port | URL |
|---------|------|-----|
| Grafana | 3000 | http://localhost:3000 |
| Prometheus | 9091 | http://localhost:9091 |
| cAdvisor | 8080 | http://localhost:8080 |
| Node Exporter | 9100 | http://localhost:9100 |
| Quant API | 9011 | http://localhost:9011 |
| Freqtrade REST | 9013 | http://localhost:9013 |

## Security Notes

- Change default Grafana password before production use
- Consider enabling HTTPS for Grafana
- Restrict access to Prometheus and cAdvisor endpoints
- Use Docker secrets for sensitive configuration
