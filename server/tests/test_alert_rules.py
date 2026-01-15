import sys
import os
import unittest
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Add server directory to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models import Base, Server, User, AlertRule, AlertRecipient
from app.main import get_alert_recipients

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
        
        # Recipient Global (Should be IGNORED in new logic)
        r1 = AlertRecipient(email="global@test.com", name="Global")
        self.session.add(r1)

        # User subscribed (Should be IGNORED unless assigned)
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
        # Should match: Global Rule, Srv1 Rule, GroupA Rule
        # Ignored: Global Recipient, User (not assigned)
        recipients, rules = get_alert_recipients(self.session, srv1, "cpu")
        # Recipients is now a list of strings
        emails = sorted(recipients)
        
        expected = sorted([
            "rule_global@test.com", 
            "rule_srv1@test.com", 
            "rule_groupA@test.com"
        ])
        print(f"Test Case 1 Emails: {emails}")
        self.assertEqual(emails, expected)
        
        # Verify rules logged
        # Global AlertRecipients and Subscribed Users are no longer logged/added
        self.assertTrue(any(f"{rule_global.id}" in str(r) for r in rules)) # basic check on rule logging
        
        # Test Case 2: srv2 (Group B) - CPU Alert
        # Should match: Global Rule.
        # Should NOT match: Srv1 Rule, GroupA Rule.
        recipients, rules = get_alert_recipients(self.session, srv2, "cpu")
        emails = sorted(recipients)
        
        expected = sorted([
            "rule_global@test.com"
        ])
        print(f"Test Case 2 Emails: {emails}")
        self.assertEqual(emails, expected)

        # Test Case 3: srv3 (No Group) - CPU Alert
        # Should match: Global Rule.
        recipients, rules = get_alert_recipients(self.session, srv3, "cpu")
        emails = sorted(recipients)
        print(f"Test Case 3 Emails: {emails}")
        self.assertEqual(emails, expected)
        
        # Test Case 4: srv1 - Memory Alert
        # Should match: Memory Rule.
        recipients, rules = get_alert_recipients(self.session, srv1, "memory")
        emails = sorted(recipients)
        
        expected_mem = sorted([
            "rule_mem@test.com"
        ])
        print(f"Test Case 4 Emails: {emails}")
        self.assertEqual(emails, expected_mem)

if __name__ == '__main__':
    unittest.main()
