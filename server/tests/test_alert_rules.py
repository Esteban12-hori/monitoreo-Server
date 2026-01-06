import sys
import os
import unittest
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Add server directory to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models import Base, Server, User, AlertRule, AlertRecipient
from app.alert_logic import get_alert_recipients

class TestAlertRules(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self):
        self.session.close()

    def test_alert_logic(self):
        # Setup Data
        # Server 1 in Group A
        srv1 = Server(server_id="srv1", token="t1", group_name="groupA")
        # Server 2 in Group B
        srv2 = Server(server_id="srv2", token="t2", group_name="groupB")
        # Server 3 (No group)
        srv3 = Server(server_id="srv3", token="t3")
        
        self.session.add_all([srv1, srv2, srv3])
        
        # Recipient Global
        r1 = AlertRecipient(email="global@test.com", name="Global")
        self.session.add(r1)

        # User subscribed
        u1 = User(email="user@test.com", password_hash="hash", receive_alerts=True, is_admin=True)
        self.session.add(u1)

        # Rules
        # 1. Global CPU Rule
        rule_global = AlertRule(
            alert_type="cpu",
            server_scope="global",
            emails=json.dumps(["rule_global@test.com"])
        )
        # 2. Server Specific Rule (srv1)
        rule_srv1 = AlertRule(
            alert_type="cpu",
            server_scope="server",
            target_id="srv1",
            emails=json.dumps(["rule_srv1@test.com"])
        )
        # 3. Group Specific Rule (groupA)
        rule_groupA = AlertRule(
            alert_type="cpu",
            server_scope="group",
            target_id="groupA",
            emails=json.dumps(["rule_groupA@test.com"])
        )
        # 4. Memory Rule (should not match CPU)
        rule_mem = AlertRule(
            alert_type="memory",
            server_scope="global",
            emails=json.dumps(["rule_mem@test.com"])
        )
        
        self.session.add_all([rule_global, rule_srv1, rule_groupA, rule_mem])
        self.session.commit()

        # Test Case 1: srv1 (Group A) - CPU Alert
        # Should match: Global Recipient, User, Global Rule, Srv1 Rule, GroupA Rule
        recipients, rules = get_alert_recipients(self.session, srv1, "cpu")
        emails = sorted([r['email'] for r in recipients])
        
        expected = sorted([
            "global@test.com", 
            "user@test.com", 
            "rule_global@test.com", 
            "rule_srv1@test.com", 
            "rule_groupA@test.com"
        ])
        print(f"Test Case 1 Emails: {emails}")
        self.assertEqual(emails, expected)
        
        # Verify rules logged
        self.assertTrue(any("Global AlertRecipients" in r for r in rules))
        self.assertTrue(any("Subscribed Users" in r for r in rules))
        self.assertTrue(any(f"Rule(id={rule_global.id}" in r for r in rules))
        self.assertTrue(any(f"Rule(id={rule_srv1.id}" in r for r in rules))
        self.assertTrue(any(f"Rule(id={rule_groupA.id}" in r for r in rules))
        
        # Test Case 2: srv2 (Group B) - CPU Alert
        # Should match: Global Recipient, User, Global Rule.
        # Should NOT match: Srv1 Rule, GroupA Rule.
        recipients, rules = get_alert_recipients(self.session, srv2, "cpu")
        emails = sorted([r['email'] for r in recipients])
        
        expected = sorted([
            "global@test.com", 
            "user@test.com", 
            "rule_global@test.com"
        ])
        print(f"Test Case 2 Emails: {emails}")
        self.assertEqual(emails, expected)

        # Test Case 3: srv3 (No Group) - CPU Alert
        # Should match: Global Recipient, User, Global Rule.
        recipients, rules = get_alert_recipients(self.session, srv3, "cpu")
        emails = sorted([r['email'] for r in recipients])
        print(f"Test Case 3 Emails: {emails}")
        self.assertEqual(emails, expected)
        
        # Test Case 4: srv1 - Memory Alert
        # Should match: Global Recipient, User, Memory Rule.
        recipients, rules = get_alert_recipients(self.session, srv1, "memory")
        emails = sorted([r['email'] for r in recipients])
        
        expected_mem = sorted([
            "global@test.com", 
            "user@test.com", 
            "rule_mem@test.com"
        ])
        print(f"Test Case 4 Emails: {emails}")
        self.assertEqual(emails, expected_mem)

if __name__ == '__main__':
    unittest.main()
