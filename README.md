<!-- markdownlint-disable-next-line -->
# <img src="https://cdn.bfldr.com/B686QPH3/at/w5hnjzb32k5wcrcxnwcx4ckg/Dynatrace_signet_RGB_HTML.svg?auto=webp&format=pngg" alt="DT logo" width="30"> Log Pipelines with BindPlane

[![Dynatrace](https://img.shields.io/badge/Dynatrace-Intelligence-purple?logo=dynatrace&logoColor=white)](https://dynatrace-wwse.github.io/codespaces-framework/dynatrace-integration/#mcp-server-integration)
[![Mastering](https://img.shields.io/badge/Mastering-Complexity-8A2BE2?logo=dynatrace)](https://dynatrace-wwse.github.io)
[![Downloads](https://img.shields.io/docker/pulls/shinojosa/dt-enablement?logo=docker)](https://hub.docker.com/r/shinojosa/dt-enablement)
[![Integration tests](https://github.com/dynatrace-wwse/enablement-bindplane-logs/actions/workflows/integration-tests.yaml/badge.svg)](https://github.com/dynatrace-wwse/enablement-bindplane-logs/actions)
[![Version](https://img.shields.io/github/v/release/dynatrace-wwse/enablement-bindplane-logs?color=blueviolet)](https://github.com/dynatrace-wwse/enablement-bindplane-logs/releases)
[![Commits](https://img.shields.io/github/commits-since/dynatrace-wwse/enablement-bindplane-logs/latest?color=ff69b4&include_prereleases)](https://github.com/dynatrace-wwse/enablement-bindplane-logs/graphs/commit-activity)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?color=green)](https://github.com/dynatrace-wwse/enablement-bindplane-logs/blob/main/LICENSE)
[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live-green)](https://dynatrace-wwse.github.io/enablement-bindplane-logs/)

---

[![Log Pipeline Overview](docs/img/hero.png)](docs/img/hero.png)

## Lab Overview

During this hands-on training, you will install and configure BindPlane to collect logs from a Linux host, shape them in-flight using processors and routers, and deliver them to Dynatrace, where OpenPipeline takes over to parse and shape them.

**Lab tasks:**

1. **Getting Started**
   - Create a BindPlane account and project
   - Generate a Dynatrace platform token with `logs.ingest` and `metrics.ingest` permissions
   - Launch the lab environment using GitHub Codespaces or a local Dev Container

2. **Install the BindPlane Agent**
   - Run the BindPlane-generated installation command on the lab host
   - Confirm the agent appears in the BindPlane UI

3. **Create a BindPlane Configuration**
   - Define a File source pointed at the host's syslog
   - Configure a Dynatrace destination using your environment ID and token
   - Assign the agent to the configuration and verify data flowing in the pipeline overview

4. **Add Fields with a Processor**
   - Use the live log preview in BindPlane to inspect in-flight records
   - Apply an *Add Fields* transform processor to tag every log with a `project` attribute
   - Roll out the configuration change and confirm the new field appears in Dynatrace Logs

5. **Parse Logs with Dynatrace OpenPipeline**
   - Create an OpenPipeline logs pipeline using the Syslog technology bundle
   - Tune the processor matching condition to align with the lab's log file path
   - Route logs to the pipeline using a dynamic route keyed on the `project` field
   - Verify raw syslog content is now fully parsed into discrete, queryable fields

6. **Mask Sensitive Data & Route Selectively**
   - Identify plaintext credentials leaking through syslog audit logs
   - Add a BindPlane *Redact Sensitive Data* processor with custom regex rules and a hashing strategy
   - Insert a BindPlane router to limit redaction to only credential-bearing logs
   - Confirm hashed values replace the originals in Dynatrace

7. **Extract Metrics from Logs**
   - Generate counter metrics from structured log data using OpenPipeline metric extraction

8. **Monitor BindPlane Health**
   - Observe the health of your BindPlane infrastructure using Self-Monitoring (SFM)

Ready to build a log pipeline?

## 🚀 Open the lab

[https://dynatrace-wwse.github.io/enablement-bindplane-logs](https://dynatrace-wwse.github.io/enablement-bindplane-logs)
