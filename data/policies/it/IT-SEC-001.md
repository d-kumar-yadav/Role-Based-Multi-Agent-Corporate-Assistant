---
doc_id: IT-SEC-001
title: Acceptable Use and Security Rules
department: it
access_level: internal
roles: [employee, manager, it]
owner: IT Security Team
version: "1.0"
effective_date: 2026-10-11
review_date: 2027-04-09
systems: []
tags: ["acceptable use","security","password policy","device management","incident reporting"]
related_docs: [IT-RUNBOOK-001, IT-ASSET-001]
classification: "Internal — IT"
---

## Purpose and Scope
This document defines rules for the acceptable use of Company IT resources, devices, and data, and the security practices all users must follow to protect Company and client information.

## Acceptable Use of Company Devices
Company‑issued devices (laptops, phones, tablets) are provided for business use. Limited personal use is permitted provided it does not:

- Interfere with work responsibilities.  
- Involve illegal, offensive, or Company policy‑violating content.  
- Consume excessive bandwidth or storage in a way that impacts business operations.  
- Involve installation of unapproved software (see Section 5).

All activity on Company devices and networks may be monitored for security purposes, in accordance with applicable law and the Company’s data protection notices.

## Password and Authentication Policy
- Minimum password length: 12 characters, with complexity requirements (uppercase, lowercase, number, symbol).  
- Multi‑factor authentication (MFA) is mandatory for all accounts accessing Company systems, without exception.  
- Passwords must not be reused across the last 10 password changes.  
- Passwords must never be shared, written down in unsecured locations, or transmitted via chat/email.  
- Default credentials on any new system or device must be changed before deployment.

## Data Classification and Handling

| Classification | Examples | Handling Requirement |
|---|---|---|
| Public | Marketing materials, published blog posts | No restriction |
| Internal | Internal policies, org charts | Company network/devices only |
| Confidential | Financial data, HR records, client contracts | Role-based access, encryption at rest |
| Restricted | Credentials, encryption keys, legal/litigation material | Named-individual access only, audit logged |

## Software Installation Rules
Only software from the approved Software Catalog (KB-IT-0045) may be installed on Company devices. Requests for new software require:

1. Business justification submitted via the IT portal.  
2. Security review by the IT Security team (data handling, vendor security posture).  
3. Procurement approval if a paid license is involved.

Browser extensions, developer tools, and open‑source packages used in Company codebases are subject to a lighter‑weight review focused on known vulnerability scanning.

## BYOD (Bring Your Own Device) Policy
Personal devices may be used to access Company email and calendar only, subject to enrollment in the Mobile Device Management (MDM) system, which enforces a device passcode and remote‑wipe capability for Company data. Personal devices may not be used to access Confidential or Restricted data under any circumstances.

## Remote Access and VPN Rules
- VPN must be used for all access to internal systems from outside the corporate network.  
- Split‑tunneling is disabled by default; exceptions require IT Security approval.  
- Public Wi‑Fi use for Company work requires VPN connection at all times.  
- VPN sessions automatically time out after 8 hours of inactivity and require reauthentication.

## Prohibited Activities
The following are strictly prohibited on Company systems and networks:

- Attempting to access systems or data outside one’s authorized role scope.  
- Installing or using unauthorized remote access tools.  
- Disabling or tampering with endpoint security agents.  
- Using Company systems for cryptocurrency mining or unrelated commercial activity.  
- Sharing login credentials with any other individual, including colleagues.  
- Connecting unauthorized external storage devices to Company laptops.

## Incident Reporting
Any suspected security incident — phishing email, lost/stolen device, suspected malware, unauthorized access — must be reported immediately to **securityincident@meridianglobal.example** or via the emergency IT hotline, regardless of time of day. Do not attempt to investigate or remediate a suspected breach independently; early containment by the Security team is critical.

Reported incidents are triaged using the Severity matrix defined in the IT Runbooks document, with SEV‑1/SEV‑2 incidents triggering the Security Incident Response Plan.

## Security Awareness Training
All employees are required to complete security awareness training within 2 weeks of joining and annually thereafter, covering phishing recognition, password hygiene, and data handling practices. Completion is tracked centrally and non‑completion beyond the deadline is escalated to the employee’s manager.

Periodic simulated phishing tests are conducted; employees who fail are required to complete supplemental training.

## Third‑Party and Vendor Access
External vendors requiring access to Company systems must go through a security review and be provisioned with time‑limited, role‑scoped access only. All third‑party access is logged and reviewed quarterly by IT Security, and automatically revoked at contract end unless explicitly renewed.

## Consequences of Violation
Violations of this policy may result in disciplinary action up to termination, and where applicable, legal action or reporting to relevant authorities, particularly in cases involving data theft, unauthorized access, or deliberate security circumvention. Repeated inadvertent violations (e.g., failed phishing tests, unapproved software installs) are addressed through additional training in the first instance.

## Contact
Security questions and policy exceptions should be directed to **security@meridianglobal.example**. Incidents should always go through the emergency channel described in Section 9, not general email.

## Revision History
| Version | Effective Date | Author | Description |
|---------|----------------|--------|-------------|
| 1.0 | 2026-10-11 | IT Security Team | Initial version |

## Document Control
| Owner | Approver | Distribution | Review Cycle |
|-------|----------|--------------|--------------|
| IT Security Team | IT Management | All Employees | Annual |
