---
doc_id: IT-ASSET-001
title: Software and Asset Catalog
department: it
access_level: internal
roles: [employee, manager, it]
owner: IT Infrastructure Team
version: "1.0"
effective_date: 2026-10-11
review_date: 2027-04-09
systems: [Slack, Zoom, VS Code, JetBrains, Git, Docker Desktop, Figma, Adobe Creative Cloud, Jira, Linear, Asana, Tableau, dbt, Snowflake, 1Password]
tags: [software catalog, asset lifecycle, hardware configuration, license management, vendor tools]
related_docs: [IT-RUNBOOK-001, IT-SEC-001, CROSS-EQUIP-001]
classification: "Internal — IT"
---

## Purpose
This catalog lists all software approved for installation on Company devices, standard hardware configurations by role, and asset lifecycle rules. It is referenced by the Laptop Provisioning and Software Installation runbooks.

## Approved Software by Category
| Category                              | Approved Tools                                          | Approval Needed                |
|---------------------------------------|----------------------------------------------------------|--------------------------------|
| Company Workspace (email, Productivity Suite) | Docs, Sheets, Slides (pre‑installed)                     | None — pre‑installed           |
| Communication                         | Slack, Zoom                                               | None — pre‑installed           |
| Development (Engineering)             | VS Code, JetBrains suite, Git, Docker Desktop             | Team Lead                      |
| Design                                | Figma, Adobe Creative Cloud                               | Manager                        |
| Project Management                    | Jira, Linear, Asana                                       | Manager                        |
| Data & Analytics                      | Tableau, dbt, Snowflake                                   | Department Head                |
| Endpoint agent (mandatory, Security)  | 1Password                                                 | None — mandatory pre‑installed |

Any tool not listed above must go through the Software Installation Rules process described in the IT Acceptable Use & Security Rules document before installation.

## Standard Hardware Configuration by Role
| Role                     | Laptop Spec                              | Additional Equipment                     |
|--------------------------|------------------------------------------|------------------------------------------|
| Engineering              | 16‑core CPU, 32 GB RAM, 1 TB SSD          | External monitor, docking station        |
| Design                   | Apple Silicon, 32 GB RAM, 1 TB SSD       | Color‑calibrated monitor                 |
| Sales & Customer‑facing  | Standard 16 GB RAM, 512 GB SSD           | Noise‑cancelling headset                |
| General / Admin          | Standard 16 GB RAM, 256 GB SSD           | None                                     |
| Executive                | Premium ultraportable, 32 GB RAM         | Mobile hotspot device                    |

Requests for configuration above the standard for a role require Department Head approval, logged against the asset request in the IT portal.

## Asset Lifecycle
| Stage        | Policy                                                                                                                                                     |
|--------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| New          | Asset issued within 3 working days of provisioning confirmation (start date).                                                                            |
| Refresh      | Laptops refreshed every 3 years; phones refreshed every 2 years.                                                                                           |
| Repair       | Hardware faults logged as SEV‑3, loaner issued. Repair issued within 1 business day if repair exceeds 2 days.                                            |
| Return       | All assets returned within 5 working days of the last working day per off‑boarding runbook.                                                               |
| Decommissioned| Assets wiped per NIST data sanitization standard and recycled via approved e‑waste vendor.                                                             |

## License Management
Software licenses are tracked centrally in the Asset Management system, linked to individual employee IDs. Named‑user licenses are reassigned within 48 hours of an employee’s exit, following the off‑boarding runbook. Floating/concurrent licenses (e.g., design tools shared across a team) are managed by the relevant Department Head in coordination with IT.

Any department wishing to add a new named‑user license for an existing approved tool should raise a request via the IT portal rather than purchasing directly, to ensure central visibility of license counts for renewal negotiations.

## Ticket Categories
| Category               | Examples                                 | Default Severity |
|------------------------|------------------------------------------|------------------|
| Access Request         | New account, permission change           | SEV‑4            |
| Hardware Issue         | Laptop fault, peripheral not working     | SEV‑3            |
| Software Issue         | Application crash, install failure       | SEV‑3            |
| Network/Connectivity   | VPN failure, Wi‑Fi issue                 | SEV‑2 to SEV‑3   |
| Security Incident      | Phishing, suspected malware              | SEV‑1 to SEV‑2   |
| New Asset Request      | Laptop, monitor, peripherals             | SEV‑4            |

## Vendor‑Managed Tools
- CRM platform — owned by Sales Operations  
- Marketing automation platform — owned by Marketing  
- HRIS (HR portal) — owned by HR, IT provides infrastructure support only  
- Finance ERP — owned by Finance, IT provides infrastructure support only  

Access provisioning for these tools follows the owning department’s approval process, with IT executing the technical account creation upon confirmed approval.

## Requesting a New Tool
Employees seeking to request a tool not on this catalog should submit a request via the IT portal, including business justification and expected number of users. Requests are reviewed on a rolling basis, typically within 5 business days, following the review process outlined in the IT Acceptable Use & Security Rules document (Section 5).

## Contact
For catalog updates or license availability questions, contact **itassets@meridianglobal.example**.

## Revision History
| Version | Effective Date | Author                     | Description       |
|---------|----------------|----------------------------|-------------------|
| 1.0     | 2026-10-11     | IT Infrastructure Team     | Initial version   |

## Document Control
| Owner                | Approver               | Distribution          | Review Cycle |
|----------------------|------------------------|-----------------------|--------------|
| IT Infrastructure Team | IT Infrastructure Team | All IT staff          | Annual       |
