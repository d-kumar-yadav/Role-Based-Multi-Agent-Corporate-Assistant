---
doc_id: IT-TEAM-001
title: IT Helpdesk and Team Structure
department: it
access_level: it_only
roles: [it]
owner: IT Infrastructure Team
version: "1.0"
effective_date: 2026-10-11
review_date: 2027-04-09
systems: []
tags: ["IT Helpdesk","Team Structure","Escalation","Support","Roles"]
related_docs: [IT-RUNBOOK-001, IT-SEC-001, IT-ASSET-001]
classification: "Internal — IT"
---

## Purpose
This document describes how the IT function is organized internally — team structure, escalation chain, and exactly who owns what — complementing the IT Runbooks (which describe how to fix things) and the IT Acceptable Use rules (which describe policy).

## IT Team Structure
Head of IT  
|  
+-- Infrastructure Team Lead  
|   |  
|   +-- Network Engineers (2)  
|   +-- Systems Administrators (3)  
|  
+-- Application Support Lead  
|   |  
|   +-- App Support Engineers (3)  
|  
+-- IT Security Team Lead (reports jointly to Head of IT and CISO)  
|   |  
|   +-- Security Analysts (2)  
|  
+-- IT Helpdesk Lead  
|  
+-- Helpdesk/Support Technicians (4)  

Total IT function headcount: approximately 16, supporting roughly 410 employees across three office locations plus remote staff.

## Helpdesk Tiering
| Tier | Handles | Typical Staff |
|------|---------|---------------|
| Tier 1 (Helpdesk) | Password resets, access requests, basic hardware/software issues | Helpdesk Technicians |
| Tier 2 (App/Infra Support) | Application errors, network issues, server‑level problems, complex infrastructure | App Support Engineers, Systems Administrators, Infrastructure Team Lead |
| Tier 3 (Specialist) | Security incidents, architecture‑level problems, company‑wide outages, vendor escalations | Security Team Lead |
| Tier 4 (Leadership) | Budget/architecture decisions | Head of IT, CTO |

A ticket that cannot be resolved within the response‑time targets defined in the IT Runbooks (Section 2, Incident Severity Levels) is automatically escalated to the next tier.

## Who Owns What (Quick Reference)
| Area | Owner |
|------|-------|
| Laptop/hardware provisioning (per Software & Asset Catalog) | Helpdesk Technicians |
| Network and connectivity | Network Engineers |
| Servers and infrastructure | Systems Administrators |
| Internal applications (non‑vendor‑managed) | App Support Engineers |
| Security incidents and access reviews | IT Security Team |
| VPN and remote access (policy exceptions) | Network Engineers, escalating to Security |
| Software licensing, tracked in Asset Management system | Infrastructure Team Lead |

## Escalation Contacts by Severity
| Severity | First Contact | Time / Notes |
|----------|---------------|--------------|
| SEV‑1 (Critical) | On‑call Infrastructure Engineer via paging system, then Head of IT | If unresolved in target time |
| SEV‑2 (High) | On‑call App/Infra Support Relevant Team Lead | Helpdesk ticket routed by |
| SEV‑3 (Medium) | Tier 2 owner per Section 4 category | N/A — resolved within |
| SEV‑4 (Low) | Helpdesk ticket | Helpdesk SLA |

Security incidents (regardless of severity) always route to the Security Team first per the Incident Reporting process in the IT Acceptable Use & Security Rules document, not through the general helpdesk tiering above.

## Cross‑Functional IT Contacts
| Situation | Who to Involve |
|-----------|----------------|
| New hire needs equipment (Helpdesk triggered automatically from HR onboarding workflow) | Helpdesk |
| Employee exit needs access revoked | Helpdesk, per the Offboarding Runbook |
| New department wants a new tool | Infrastructure Team Lead (security review), IT Security Team (mandatory review before provisioning) |
| Vendor wants system access | IT Security Team (mandatory review before provisioning) |

## On‑Call Structure
The Infrastructure and Application Support teams jointly maintain a 24 × 7 on‑call rotation, one engineer per week per function, published on the internal on‑call calendar. The Security Team maintains a separate, always‑active on‑call line specifically for security incidents, since these require immediate response regardless of standard business hours.

## Common Questions This Document Answers
- “Who do I contact if my laptop breaks?” — Helpdesk Technicians (Tier 1), see Section 3.  
- “What’s the structure of the IT team?” — see Section 2.  
- “Who handles a security incident?” — IT Security Team directly, bypassing normal tiering (Section 5).  
- “Who approves a new software request?” — Infrastructure Team Lead, per Section 4 and the Software & Asset Catalog.

## Contact
For questions about IT team structure or escalation ownership not covered above, contact **it-support@meridianglobal.example**.

## Revision History
| Version | Date | Author | Description |
|---------|------|--------|-------------|
| 1.0 | 2026-10-11 | IT Infrastructure Team | Initial version |

## Document Control
| Owner | Approver | Distribution | Review Cycle |
|-------|----------|--------------|--------------|
| IT Infrastructure Team | Head of IT | IT Team | Annual |
