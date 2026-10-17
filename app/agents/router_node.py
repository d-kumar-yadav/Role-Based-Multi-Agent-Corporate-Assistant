KEYWORD_ROUTING = {
    "hr":      ["leave", "vacation", "compensation", "salary", "recruit",
                "hiring", "onboard", "benefits", "handbook",
                "posh", "grievance", "performance", "promotion",
                "maternity", "paternity", "sabbatical", "attendance"],
    "finance": ["expense", "reimburse", "refund", "budget", "revenue",
                "invoice", "vendor", "procurement", "audit", "tax",
                "purchase order", "per diem", "travel", "entertainment",
                "corporate card", "po "],
    "it":      ["vpn", "laptop", "monitor", "password", "software",
                "access", "security", "runbook", "ticket", "asset",
                "network", "device", "on-call", "headset", "docking"],
}

CROSS_DOMAIN_PAIRS = [
    ({"it", "finance"}, ["reimburse", "refund", "purchase", "monitor",
                         "laptop", "device", "equipment", "docking"]),
    ({"hr", "it"},      ["onboard", "exit", "offboard"]),
    ({"hr", "finance"}, ["payroll", "bonus", "compensation"]),
]


def router_node(state: dict) -> dict:
    query = (state.get("query") or "").lower()
    matched = set()

    for domain, keywords in KEYWORD_ROUTING.items():
        if any(kw in query for kw in keywords):
            matched.add(domain)

    for pair_domains, pair_keywords in CROSS_DOMAIN_PAIRS:
        if any(kw in query for kw in pair_keywords) and any(d in matched for d in pair_domains):
            matched.update(pair_domains)

    if not matched:
        return {"domains": ["hr"]}

    return {"domains": sorted(matched)}
