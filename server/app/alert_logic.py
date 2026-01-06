from sqlalchemy.orm import Session
from sqlalchemy import select, or_
import json
from .models import Server, AlertRecipient, User, AlertRule

def get_alert_recipients(sess: Session, server: Server, alert_type: str) -> tuple[list, list[str]]:
    applied_rules_info = []

    # 1. Global AlertRecipients
    global_recipients = sess.execute(select(AlertRecipient)).scalars().all()
    recipients = [{"email": r.email, "name": r.name} for r in global_recipients]
    if global_recipients:
        applied_rules_info.append("Global AlertRecipients")

    # 2. Users with receive_alerts=True (Global subscription)
    alert_users = sess.execute(select(User).where(User.receive_alerts == True)).scalars().all()
    users_added = 0
    for u in alert_users:
        # Include if admin OR has access to this server
        if u.is_admin or any(s.server_id == server.server_id for s in u.servers):
            recipients.append({"email": u.email, "name": u.name})
            users_added += 1
    if users_added > 0:
        applied_rules_info.append(f"Subscribed Users ({users_added})")
    
    # 3. Alert Rules
    # Match: alert_type AND (scope=global OR scope=server+id OR scope=group+name)
    rules_query = select(AlertRule).where(AlertRule.alert_type == alert_type)
    
    # Filter conditions for scope
    conditions = [AlertRule.server_scope == 'global']
    conditions.append((AlertRule.server_scope == 'server') & (AlertRule.target_id == server.server_id))
    if server.group_name:
        conditions.append((AlertRule.server_scope == 'group') & (AlertRule.target_id == server.group_name))
    
    rules = sess.execute(rules_query.where(or_(*conditions))).scalars().all()

    for r in rules:
        applied_rules_info.append(f"Rule(id={r.id}, scope={r.server_scope}, target={r.target_id})")
        try:
            emails = json.loads(r.emails)
            for email in emails:
                recipients.append({"email": email, "name": "Rule Recipient"})
        except:
            pass

    # Deduplicate
    unique = {r["email"]: r for r in recipients}.values()
    return list(unique), applied_rules_info
