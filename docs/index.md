In this hands-on lab, you're going to build a Telemetry Pipeline end-to-und. Using **BindPlane** as your collection and processing layer and **Dynatrace** as your observability backend, you'll collect syslog data from a Linux host, shape it in-flight, and deliver it to Dynatrace — where **OpenPipeline** takes over to parse and further enrich it.

By the end of the lab, you'll know how to:

- Deploy and configure a BindPlane agent on a Linux host
- Define sources, processors, and destinations in a BindPlane configuration
- Enrich logs with custom metadata before they leave the host
- Parse structured fields out of raw syslog content using Dynatrace OpenPipeline
- Detect and mask sensitive credentials in-flight using regex-based redaction
- Route logs selectively so only the right data passes through each processor
- Convert log events into metrics and query them with DQL
- Monitor the health of your BindPlane pipeline itself using self-monitoring

## Prerequisites
- BindPlane account and project
- Dynatrace tenant
- Dynatrace token with the following permissions:
    - storage:logs:write
    - openpipeline:logs:ingest
    - storage:metrics:write
    - openpipeline:metrics:ingest
- One of:
    - For working entirely in a browser: access to GitHub Codespaces
    - For working locally in a [Dev Container](https://code.visualstudio.com/docs/devcontainers/tutorial):
        - VSCode
        - Dev Containers Extension installed
        - Docker
(more about this in the next section)

<div class="grid cards" markdown>
- [Yes! Let's begin :octicons-arrow-right-24:](2-getting-started.md)