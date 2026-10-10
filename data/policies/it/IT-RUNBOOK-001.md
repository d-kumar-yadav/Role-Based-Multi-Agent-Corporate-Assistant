---
doc_id: IT-RUNBOOK-001
title: IT Runbooks and Support Procedures
department: it
access_level: it_only
roles: [it]
owner: IT Infrastructure Team
version: "1.0"
effective_date: 2026-10-11
review_date: 2027-04-09
systems: [Identity Management, VPN, Backup, Change Management, Asset Management]
tags: [runbooks, incident management, IT support, procedures, escalation]
related_docs: [IT-SEC-001, IT-TEAM-001, IT-ASSET-001]
classification: "Internal — IT"
---

## Purpose and Scope
This document provides standard operating procedures and runbooks for the IT Support team to handle common incidents, requests, and maintenance tasks consistently across the organization.

## Incident Severity Levels
| Severity | Definition                                   | Response Time | Resolution Target |
|----------|----------------------------------------------|---------------|-------------------|
| SEV-1 (Critical) | Outage, production down, major feature/system | 15 minutes | 4 hours |
| SEV-2 (High) | Impaired, multiple users affected | 30 minutes | 8 hours |
| SEV-3 (Medium) | Single user or non‑critical system affected | 4 hours | 2 business days |
| SEV-4 (Low) | Cosmetic issue, or general request | 1 business day | 5 business days |

## Standard Operating Procedure — Password Reset
1. Verify requester identity via employee ID and registered email/phone (voice verification for phone requests).  
2. Initiate reset through the Identity Management console.  
3. Enforce password complexity requirements (minimum 12 characters, mixed case, number, symbol).  
4. Send reset link to the employee’s registered email only — never share temporary passwords via chat or phone.  
5. Log the reset in the ticketing system with timestamp and verification method used.

## Standard Operating Procedure — VPN Setup
1. Confirm employee’s role and remote access approval in the Identity Management system.  
2. Provision VPN client license and generate a unique certificate for the device.  
3. Guide employee through client installation using the standard onboarding guide (KB-IT-0032).  
4. Test connectivity to at least two internal resources before closing the ticket.  
5. VPN access is auto‑revoked upon employee exit as part of the off‑boarding workflow (Section 9).

## Standard Operating Procedure — Laptop Provisioning
1. Confirm asset request approval from the New Hire Onboarding workflow.  
2. Image laptop with the standard corporate build (OS version, endpoint security agent, MDM enrollment).  
3. Pre‑install approved software bundle based on department (see Software Catalog, KB-IT-0045).  
4. Register asset tag in the Asset Management system, linked to employee ID.  
5. Hand over with signed Asset Acceptance form (digital, via IT portal).

## Standard Operating Procedure — Server Restart
1. Confirm restart is not scheduled during a business‑critical window (check Change Calendar).  
2. Notify affected team via the #it-maintenance channel at least 30 minutes in advance for non‑emergency restarts.  
3. Take a pre‑restart health snapshot (CPU, memory, active connections).  
4. Execute restart following the service‑specific runbook (see individual service runbooks in the Infra wiki).  
5. Verify service health post‑restart against baseline metrics before closing the maintenance window.

## Standard Operating Procedure — Backup Verification
Backups are run nightly for all production databases and weekly for file servers.

**Backup verification runbook:**  
1. Confirm backup job completed successfully in the backup console (no failed‑job alerts).  
2. Perform a random restore test on a non‑production environment monthly.  
3. Verify restored data integrity against a checksum of the source.  
4. Log verification results in the Backup Compliance tracker.  
5. Escalate any failed backup job as SEV‑2 if it affects production databases.

## Escalation Matrix
| Issue Type | First Responder | Final Escalation (no resolution within 30 min) |
|------------|----------------|-----------------------------------------------|
| Network outage | On‑call Network Engineer | Infra Team Lead → Head of IT |
| Application down | On‑call App Support | Engineering On‑call → CTO |
| Security incident | On‑call Security Team | Lead → CISO |
| Access/account issue | IT Helpdesk | IT Support Lead → Head of IT |

## Off‑boarding Runbook
Upon receipt of an off‑boarding request from HR:  
1. Disable all account access (email, VPN, SSO, internal tools) at the exact time specified by HR.  
2. Revoke all active sessions and API tokens associated with the employee.  
3. Retrieve and wipe company‑issued devices per the Asset Return process.  
4. Archive employee’s email and files per the Data Retention Policy (typically 90 days before permanent deletion).  
5. Update Asset Management system to reflect returned/decommissioned status.

## On‑Call Rotation
IT maintains a 24×7 on‑call rotation across Network, Application Support, and Security functions, each on a weekly rotation published in the on‑call calendar. On‑call engineers are required to acknowledge SEV‑1/SEV‑2 pages within the response‑time targets in Section 2, escalating automatically if unacknowledged.

## Change Management Process
All production changes (deployments, configuration changes, infrastructure updates) must be logged in the Change Management system with:  

- Description of the change and rollback plan  
- Risk assessment (Low/Medium/High)  
- Scheduled window (avoiding business‑critical periods)  
- Approver sign‑off (Team Lead for Low risk, Infra Head for Medium/High risk)  

Emergency changes outside a scheduled window require verbal approval from the Infra Team Lead, followed by retroactive documentation within 24 hours.

## Common Troubleshooting Runbooks
- **Network Outage:** Check ISP status dashboard → verify core switch/router health → check recent change log entries → escalate to ISP if external → notify affected floors/locations via facilities.  
- **Email Service Down:** Check mail server health dashboard → verify DNS/MX records unchanged → check recent security policy changes → escalate to email service provider if platform‑side issue confirmed.  
- **Printer/Peripheral Issues:** Verify network connectivity to print server → check driver version against Software Catalog → re‑queue stuck print jobs → escalate to facilities vendor if hardware fault suspected.

## Disaster Recovery Overview
The Company maintains a documented Disaster Recovery (DR) plan with a Recovery Time Objective (RTO) of 4 hours and Recovery Point Objective (RPO) of 1 hour for production systems. DR drills are conducted twice yearly, with results reviewed by the Infra Team and reported to the CTO.

## Contact
For infrastructure escalations outside standard runbook coverage, contact the IT Infrastructure Team Lead via the on‑call paging system.

## Revision History
| Version | Effective Date | Author | Description |
|---------|----------------|--------|-------------|
| 1.0 | 2026-10-11 | IT Infrastructure Team | Initial version |

## Document Control
| Owner | Approver | Distribution | Review Cycle |
|-------|----------|--------------|--------------|
| IT Infrastructure Team | Head of IT | IT Support Team, System Administrators | Semi‑annual |
